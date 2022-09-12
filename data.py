import csv
import json
import re
import zipfile
import io

def load() -> tuple[dict[str, dict], dict[str, str]]:
	with open('data/gems.json', 'rb') as f:
		raw_gems: dict[str, dict] = json.load(f)
	gems: dict[str, dict] = {}
	for k, v in raw_gems.items():
		if k.endswith('Royale') or v['base_item'] is None:
			continue
		gems[v['base_item']['display_name']] = v

	text: dict[str, str] = {}
	with open('data/aura_skill.json', 'rb') as f:
		raw_text: list[dict] = json.load(f)
	prefixes = ['You and nearby', 'Your and nearby', 'Aura grants', 'Buff grants']
	for translation in raw_text:
		for k in translation['ids']:
			translated = translation['English'][0]
			if any(translated['string'].startswith(prefix + ' ') for prefix in prefixes):
				text[k] = translated

	return gems, text

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

def militant_faith_node_mapping(seed: int) -> dict:
	""" Maps passives nodes to their alternative nodes under militant faith"""
	with zipfile.ZipFile(r'data\MilitantFaithSeeds.zip') as zf:
		with zf.open('MilitantFaithSeeds.csv', 'r') as infile:
			reader = csv.reader(io.TextIOWrapper(infile, 'utf-8'))
			originals = next(reader)[2:]
			for _ in range(seed - 1998):
				next(reader)
			alternatives = next(reader)[2:]
	return {original: alternative for original, alternative in zip(originals, alternatives)}

def elegant_hubris_node_mapping(seed: int) -> dict:
	""" Maps passives nodes to their alternative nodes under elegant hubris"""
	with zipfile.ZipFile(r'data\ElegantHubrisSeeds.zip') as zf:
		with zf.open('ElegantHubrisSeeds.csv', 'r') as infile:
			reader = csv.reader(io.TextIOWrapper(infile, 'utf-8'))
			originals = next(reader)[2:]
			for _ in range(int(seed / 20) - 99):
				next(reader)
			alternatives = next(reader)[2:]
	return {original: alternative for original, alternative in zip(originals, alternatives)}
