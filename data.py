import csv
import json
import re
import zipfile
import io


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
