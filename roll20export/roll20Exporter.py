# -*- coding: utf-8 -*-
"""
Created on Thu Jun 11 13:06:27 2029

@author: JoergRue

Class to handle export to roll20 json
"""
from Wolke import Wolke
import Definitionen
import Objekte
import Talentbox
import os
import math
from collections import namedtuple
import logging
from Charakter import KampfstilMod
from Hilfsmethoden import Hilfsmethoden, WaffeneigenschaftException
import sys
import json
import time
import random
import re


class roll20Exporter(object):
    """exports character data into a Json file for a roll20 character sheet"""

    def __init__(self):
        pass

    def exportCharacter(self, filename):
        Wolke.Char.aktualisieren()

        # load the file into memory
        with open(filename, "r", encoding="utf8") as read_file:
            data = json.load(read_file)

        # update data
        if ("attribs" in data):
            self.updateCharacterData(data["attribs"], Wolke.Char)
        elif ("character" in data and "attribs" in data["character"]):
            self.updateCharacterData(data["character"]["attribs"], Wolke.Char)
        else:
            return False

        # write back the data into the file
        with open(filename, "w", encoding="utf8") as write_file:
            json.dump(data, write_file, indent=4, ensure_ascii = False)
        return True

    def updateCharacterData(self, attribs, char):
        self.updateAttributes(attribs, char)
        self.updateGlobalValues(attribs, char)
        self.updateFertigkeiten(attribs, char)
        self.updateUebernatuerliches(attribs, char)
        self.updateWaffen(attribs, char)
        self.updateRuestung(attribs, char)
        self.updateAusruestung(attribs, char)

    def updateAttributes(self, attribs, char):
        for key in Definitionen.Attribute:
            self.setCurrentAttrValue(attribs, key.lower(), char.attribute[key].wert)

    def updateGlobalValues(self, attribs, char):
        self.setCurrentAttrValue(attribs, "wsb", char.ws)
        self.setCurrentAttrValue(attribs, "wsg", char.wsStern)
        self.setCurrentAttrValue(attribs, "mr", char.mr)
        self.setCurrentAttrValue(attribs, "behinderung", char.be)
        self.setCurrentAttrValue(attribs, "geschwindigkeit", char.gs)
        self.setCurrentAttrValue(attribs, "kampfreflexe", 4 if "Kampfreflexe" in char.vorteile else 0)
        isZauberer = char.aspBasis + char.aspMod > 0
        isGeweiht = char.kapBasis + char.kapMod > 0
        if isZauberer:
            self.setMaxAttrValue(attribs, "energy", char.asp.wert + char.aspBasis + char.aspMod)
        if isGeweiht:
            self.setMaxAttrValue(attribs, "energy2", char.kap.wert + char.kapBasis + char.kapMod)
        self.setMaxAttrValue(attribs, "schip", char.schipsMax)

    def getTalents(self, fert, char):
        talStr = ""
        talente = sorted(fert.gekaufteTalente)
        for el2 in talente:
            if (len(talStr) > 0):
                talStr += ", "
            # code taken from pdfMeister, purpose not clear
            if el2.startswith("Gebräuche: "):
                talStr += el2[11:]
            elif el2.startswith("Mythen: "):
                talStr += el2[8:]
            elif el2.startswith("Überleben: "):
                talStr += el2[11:]
            else:
                talStr += el2
            if el2 in char.talenteVariable:
                vk = char.talenteVariable[el2]
                talStr += " (" + vk.kommentar + ")"
        return talStr

    def updateFertigkeit(self, attribs, attrName, fert, char):
        self.setCurrentAttrValue(attribs, attrName, fert.wert)
        # Talente
        self.setCurrentAttrValue(attribs, attrName + "_t", self.getTalents(fert, char))

    def updateFertigkeiten(self, attribs, char):
        attrNames = {
            "Athletik": "ath",
            "Heimlichkeit": "hei",
            "Mythenkunde": "myt",
            "Überleben": "ube",
            "Alchemie": "alc",
            "Selbstbeherrschung": "sel",
            "Wahrnehmung": "wah",
            "Handwerk":  "han",
            "Heilkunde": "hku",
            "Verschlagenheit": "ver",
            "Beeinflussung":  "bee",
            "Gebräuche": "geb",
            "Autorität": "aut",
            "Derekunde": "der",
            "Magiekunde": "mag"}

        assert len(attrNames) == len(Definitionen.StandardFerts) - 6 # nicht Kampffertigkeiten
        for fert in attrNames.keys():
            assert fert in Definitionen.StandardFerts
        additionalFerts = []
        for fertKey, fert in char.fertigkeiten.items():
            if fert.name in attrNames:
                self.updateFertigkeit(attribs, attrNames[fert.name], fert, char)
            elif fert.name.startswith("Gebräuche"): # special to replace Gebräuche
                self.updateFertigkeit(attribs, "geb", fert, char)
            elif fert.kampffertigkeit == 0:
                values = []
                values.append(fert.name)
                values.append(self.getTalents(fert, char))
                for attr in fert.attribute:
                    values.append("@{" + attr.lower() + "}")
                values.append(fert.wert)
                additionalFerts.append(values)
        if len(additionalFerts) > 0:
            appendices = ["_name", "_t", "_att1", "_att2", "_att3", "_fw"]
            self.setRepeatingAttrValuesEx(attribs, "zfertigkeiten", "zfertigkeit", appendices, additionalFerts)

        # Freie Fertigkeiten
        fferts = []
        for fert in char.freieFertigkeiten:
            if fert.wert < 1 or fert.wert > 3 or not fert.name:
                continue
            val = fert.name + " "
            for i in range(fert.wert):
                val += "I"
            fferts.append(val)
        self.setRepeatingAttrValues(attribs, "freiefertigkeiten", "ffert", fferts)

    def updateUebernatuerliches(self, attribs, char):
        # code taken from pdfMeister, pdfSechsterBlock (pull out function?)
        # Get number of talents
        talsList = []
        for f in char.übernatürlicheFertigkeiten:
            if char.übernatürlicheFertigkeiten[f].wert > 0 or\
                    len(char.übernatürlicheFertigkeiten[f].
                        gekaufteTalente) > 0:
                talsList.extend(char.übernatürlicheFertigkeiten[f].
                                gekaufteTalente)
        talsList = set(talsList)

        fertsList = []
        for f in char.übernatürlicheFertigkeiten:
            if char.übernatürlicheFertigkeiten[f].wert <= 0 and\
                    len(char.übernatürlicheFertigkeiten[f].
                        gekaufteTalente) == 0:
                continue
            fertsList.append(f)
        fertsList.sort(key = lambda x: (Wolke.DB.übernatürlicheFertigkeiten[x].printclass, x))

        # find highest talent value, talent could be in serveral fertigkeiten
        talsValues = {}
        talsFertigs = {}
        for tal in talsList:
            talsValues[tal] = 0
            talsFertigs[tal] = []
        for fert in fertsList:
            fe = char.übernatürlicheFertigkeiten[fert]
            val = fe.probenwertTalent
            for tal in fe.gekaufteTalente:
                if val > talsValues[tal]:
                    talsValues[tal] = val
                    talsFertigs[tal] = fe.attribute

        talCount = 1
        for tal, val in talsValues.items():
            self.setCurrentAttrValue(attribs, "sn" + str(talCount), val)
            mod = ""
            if tal in char.talenteVariable:
                vk = char.talenteVariable[tal]
                mod = " (" + vk.kommentar + ")"
            self.setCurrentAttrValue(attribs, "sn" + str(talCount) + "_t", tal + mod)
            fertAttrValues = {}
            for attr in Definitionen.Attribute.keys():
                fertAttrValues[attr] = 0
            for attr in talsFertigs[tal]:
                fertAttrValues[attr] = 1
            for attr in Definitionen.Attribute.keys():
                self.setCurrentAttrValue(attribs, attr + "mod_sn" + str(talCount), fertAttrValues[attr])
            talCount += 1

    def ignoreBE(self, weapon, char):
        fertigkeit = ""
        talent = ""
        if weapon.name in Wolke.DB.waffen:
            fertigkeit = Wolke.DB.waffen[weapon.name].fertigkeit
            talent = Wolke.DB.waffen[weapon.name].talent
        if not fertigkeit in char.fertigkeiten:
            return False
        kampfstilMods = KampfstilMod()
        if weapon.kampfstil in char.kampfstilMods:
            kampfstilMods = char.kampfstilMods[weapon.kampfstil]
        for values in kampfstilMods.BEIgnore:
            if values[0] == fertigkeit and values[1] == talent:
                return True
        return False

    def updateWaffen(self, attribs, char):
        weaponCount = 1
        nkWeaponCount = 1
        fkWeaponCount = 1
        for weapon in char.waffen:
            waffenwerte = char.waffenwerte[weaponCount - 1]
            # the values given from the char include modification by BE
            # the character sheet expects the values without the modification and adds the modification itself
            beMod = char.be
            # the character sheet doesn't know the kampfstil, so it is probably wrong for the case that the
            # kampfstil ignores the BE. So in that case, let's _add_ the be to the values a second time, then
            # the value is correct again after the sheet removes the BE
            if self.ignoreBE(weapon, char):
                beMod = self.be
            if type(weapon) == Objekte.Fernkampfwaffe or (weapon.name in Wolke.DB.waffen and Wolke.DB.waffen[weapon.name].talent == 'Lanzenreiten'):
                base = "fkw" + str(fkWeaponCount)
                self.setCurrentAttrValue(attribs, base + "_dmd", weapon.W6)
                self.setCurrentAttrValue(attribs, base + "_dmn", weapon.plus)
                self.setCurrentAttrValue(attribs, base + "_at", waffenwerte.AT + beMod)
                self.setCurrentAttrValue(attribs, base + "_t", weapon.anzeigename)
                fkWeaponCount += 1
            else:
                base = "w" + str(nkWeaponCount)
                self.setCurrentAttrValue(attribs, base + "_dmd", weapon.W6)
                # character sheet expects tp including kampfstil, but excluding damage bonus from KK
                # weapon.plus is without both
                # waffenwerte.TPPlus is including kampfstil and including damage bonus
                if "Kopflastig" in weapon.eigenschaften:
                    self.setCurrentAttrValue(attribs, base + "_dmn", waffenwerte.TPPlus - 2 * char.schadensbonus)
                else:
                    self.setCurrentAttrValue(attribs, base + "_dmn", waffenwerte.TPPlus - char.schadensbonus)
                # character sheet expects at including kampfstil, waffenwerte.AT is correct except for BE
                self.setCurrentAttrValue(attribs, base + "_at", waffenwerte.AT + beMod)
                self.setCurrentAttrValue(attribs, base + "_vt", waffenwerte.VT + beMod)
                self.setCurrentAttrValue(attribs, base + "_t", weapon.anzeigename)
                kl = 1 if "Kopflastig" in weapon.eigenschaften else 0
                self.setCurrentAttrValue(attribs, "kl" + base, kl)
                nkWeaponCount += 1
            weaponCount += 1

    def updateRuestung(self, attribs, char):
        if len(char.rüstung) > 0:
            el = char.rüstung[0]
            for zone in range(1, 7):
                self.setCurrentAttrValue(attribs, "wsg" + str(zone), el.rs[zone-1] + char.rsmod + char.ws)

    def updateAusruestung(self, attribs, char):
        self.setRepeatingAttrValues(attribs, "inv", "inv_line", char.ausrüstung)

    def setCurrentAttrValue(self, attribs, name, value):
        for attr in attribs:
            if "name" in attr and attr["name"] == name:
                attr["current"] = str(value)
                break
        else:
            attr = { "name": name, "current": str(value), "max": "", "id": self.generateAttrId() }
            attribs.append(attr)

    def setMaxAttrValue(self, attribs, name, value):
        for attr in attribs:
            if "name" in attr and attr["name"] == name:
                attr["max"] = str(value)
                break
        else:
            attr = { "name": name, "current": str(value), "max": str(value), "id": self.generateAttrId() }
            attribs.append(attr)

    def setRepeatingAttrValues(self, attribs, basenamePattern1, basenamePattern2, values):
        valueList = []
        for value in values:
            valueList.append([value])
        appendices = [""]
        self.setRepeatingAttrValuesEx(attribs, basenamePattern1, basenamePattern2, appendices, valueList)

    def setRepeatingAttrValuesEx(self, attribs, basenamePattern1, basenamePattern2, appendices, valueList):
        existingList = []
        # first find all existing lines
        # the lines all start with "repeating", then the first name, then an ID which is unique for the line,
        # then the second name, finally an appendix if the line contains several fields.
        # all the parts are separated by "_", which therefore must not occur in the ID
        pattern = re.compile('^'+ "repeating_" + basenamePattern1 + "_([-_\\d\\w])+_" + basenamePattern2)
        for attr in attribs:
            match = pattern.match(attr["name"])
            if match != None:
                existingName = match[0]
                if not existingName in existingList: 
                    existingList.append(existingName)
        # now replace or add the values
        # the valueList contains for each line one value per appendix
        for values in valueList:
            attrName = ""
            if len(existingList) > 0:
                attrName = existingList.pop()
            else:
                attrName = "repeating_"+ basenamePattern1  + "_" + self.generateRepeatingAttrId() + "_" + basenamePattern2
            valueIndex = 0
            for appendix in appendices:
                self.setCurrentAttrValue(attribs, attrName + appendix, values[valueIndex])
                valueIndex += 1

    def generateAttrId(self):
        # see https://app.roll20.net/forum/permalink/4258551/
        millis = int(round(time.time() * 1000))
        id = ""
        base64string = "-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"
        for e in range(0, 8):
            id += base64string[millis %64]
            millis = math.floor(millis / 64)
        for f in range(0, 12):
            id += base64string[random.randrange(0, len(base64string))]
        return id

    def generateRepeatingAttrId(self):
        id = self.generateAttrId()
        return id.replace("_", "-")
