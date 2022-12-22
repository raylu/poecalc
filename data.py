import csv
import json
import re
import zipfile
import io
from copy import deepcopy


def load() -> tuple[dict[str, dict], dict, dict]:
	with open('data/gems.json', 'rb') as f:
		raw_gems: dict[str, dict] = json.load(f)
	gems: dict[str, dict] = {}
	for k, v in raw_gems.items():
		if k.endswith('Royale') or k.endswith('Triggered'):
			continue
		if v['base_item']:
			gems[v['base_item']['display_name']] = v
		elif 'active_skill' in v:  # skills that are exclusive to items
			gems[v['active_skill']['display_name']] = v
	add_vaal_smite(gems)

	aura_translation: dict[str, str] = {}
	with open('data/aura_skill.json', 'rb') as f:
		raw_text: list[dict] = json.load(f)
	prefixes = ['You and nearby', 'Your and nearby', 'Aura grants', 'Buff grants', 'Each Mine']
	for translation in raw_text:
		for k in translation['ids']:
			translated = translation['English'][0]
			if any(translated['string'].startswith(prefix + ' ') for prefix in prefixes):
				aura_translation[k] = translation['English']

	curse_translation: dict[str, str] = {}
	with open('data/curse_skill.json', 'rb') as f:
		raw_text: list[dict] = json.load(f)
		identifiers = ['cursed enemies', 'cursed rare']
		for translation in raw_text:
			for k in translation['ids']:
				translated = translation['English'][0]
				if any(identifier in translated['string'].lower() for identifier in identifiers):
					curse_translation[k] = translation['English']

	return gems, aura_translation, curse_translation
def add_vaal_smite(gem_dict):
	"""Temporary fix to add in vaal smite manually while RePoE is not updated"""
	# todo: check RePoE for updates or get data from somewhere else
	vaal_smite = deepcopy(gem_dict["Smite"])
	vaal_smite["active_skill"]["display_name"] = "Vaal Smite"
	vaal_smite["active_skill"]["id"] = "vaal_smite"
	vaal_smite["active_skill"]["types"].append("Vaal")
	vaal_smite["base_item"]["display_name"] = "Vaal Smite"
	min_added_damage = [1, 1, 1, 1, 1, 1, 2, 2, 3, 3, 4, 5, 6, 7, 8, 10, 12, 14, 15, 17, 19, 20, 22, 24, 26, 28, 30, 32, 35, 38, 39, 41, 42, 44, 46, 47, 49, 51, 53, 55]
	max_added_damage = [7, 7, 9, 12, 17, 24, 31, 39, 49, 61, 74, 90, 109, 130, 156, 185, 219, 259, 293, 330, 358, 387, 419, 453, 490, 529, 572, 617, 666, 718, 745, 774, 803, 834, 865, 898, 932, 967, 1003, 1041]
	shock_chances = [10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15, 16, 16, 17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22, 23, 23, 24, 24, 24, 25, 25, 25, 25, 26, 26, 26, 26, 27]
	for stats, min_val, max_val, shock_chance in zip(vaal_smite["per_level"].values(), min_added_damage, max_added_damage, shock_chances):
		stats["stats"] = [{'value': min_val}, {'value': max_val}, None, None, {'value': shock_chance}] + stats["stats"][5:]
	gem_dict["Vaal Smite"] = vaal_smite
def legion_passive_mapping() -> dict:
	""" Maps names of timeless legion passives to their effects """
	# I couldn't find any of this info in the RePoE data, so I'm grabbing it from the path of building repo
	with open('data/LegionPassives.lua', 'r') as file:
		content = file.read()
		content = re.sub(r'\[(\d+)\] =', r'["\1"] =', content)  # turns integer keys into strings
		content = re.sub(r',\s+}', r'}', content)  # removes commas after the last key value pairs
		content = re.sub(r'\[(.*)\] =', r'\1:', content)  # removes brackets around keys and changes " =" to ":"
		content_dict = json.loads(content[content.find('{'):])
		return {node['dn']: node['sd'].values() for node in content_dict['nodes'].values()}


def militant_faith_node_mapping(seed: str) -> dict:
	""" Maps passives nodes to their alternative nodes under militant faith"""
	with zipfile.ZipFile(r'data/MilitantFaithSeeds.zip') as zf:
		with zf.open('MilitantFaithSeeds.csv', 'r') as infile:
			reader = csv.reader(io.TextIOWrapper(infile, 'utf-8'))
			originals = next(reader)[2:]
			for row in reader:
				if row[0] == seed:
					alternatives = row[2:]
					break
		return {original: alternative for original, alternative in zip(originals, alternatives)}


def elegant_hubris_node_mapping(seed: str) -> dict:
	""" Maps passives nodes to their alternative nodes under elegant hubris"""
	with zipfile.ZipFile(r'data/ElegantHubrisSeeds.zip') as zf:
		with zf.open('ElegantHubrisSeeds.csv', 'r') as infile:
			reader = csv.reader(io.TextIOWrapper(infile, 'utf-8'))
			originals = next(reader)[2:]
			for row in reader:
				if row[0] == seed:
					alternatives = row[2:]
					break
	return {original: alternative for original, alternative in zip(originals, alternatives)}
