import io
import json
import math
import re
import warnings
import zipfile
from enum import Enum

import sqlitedict  # type: ignore

def prepare_data() -> None:
	with open('data/gems.json', 'rb') as f:
		raw_gems: dict[str, dict] = json.load(f)
	with _sqlite_dict('gems', 'n') as gems:
		for k, v in raw_gems.items():
			if k.endswith(('Royale', 'Triggered')):
				continue
			if v['base_item']:
				gems[v['base_item']['display_name']] = v
			elif v['active_skill']:  # skills that are exclusive to items
				gems[v['active_skill']['display_name']] = v
		gems.commit()

	with _sqlite_dict('aura_translation', 'w') as aura_translation:
		with open('data/aura_skill.json', 'rb') as f:
			raw_text: list[dict] = json.load(f)
		prefixes = ['You and nearby', 'Your and nearby', 'Aura grants', 'Buff grants', 'Each Mine']
		for translation in raw_text:
			for k in translation['ids']:
				translated = translation['English'][0]
				if any(translated['string'].startswith(prefix + ' ') for prefix in prefixes):
					aura_translation[k] = translation['English']

		with open('data/buff_skill.json', 'rb') as f:
			raw_text = json.load(f)
		substrings = ['Link Skill', 'Linked Target', 'taken from your Energy']
		for translation in raw_text:
			for k in translation['ids']:
				translated = translation['English'][0]
				if any(substring.lower() in translated['string'].lower() for substring in substrings):
					aura_translation[k] = translation['English']

		aura_translation.commit()

	with open('data/curse_skill.json', 'rb') as f:
		raw_text = json.load(f)
	identifiers = ['cursed enemies', 'cursed rare']
	with _sqlite_dict('curse_translation', 'w') as curse_translation:
		for translation in raw_text:
			for k in translation['ids']:
				translated = translation['English'][0]
				if any(identifier in translated['string'].lower() for identifier in identifiers):
					curse_translation[k] = translation['English']
		curse_translation.commit()

def load() -> tuple[dict[str, dict], dict, dict]:
	gems = _sqlite_dict('gems', 'r')
	aura_translation = _sqlite_dict('aura_translation', 'r')
	curse_translation = _sqlite_dict('curse_translation', 'r')
	return gems, aura_translation, curse_translation

def _sqlite_dict(table: str, flag: str) -> sqlitedict.SqliteDict:
	return sqlitedict.SqliteDict('data.db', tablename=table, flag=flag,
			journal_mode='OFF', encode=json.dumps, decode=json.loads)

def legion_passive_mapping() -> dict:
	""" Maps names of timeless legion passives to their effects """
	# I couldn't find any of this info in the RePoE data, so I'm grabbing it from the path of building repo
	with open('data/LegionPassives.lua', 'r', encoding='utf8') as file:
		content = file.read()
		content = re.sub(r'\[(\d+)\] =', r'["\1"] =', content)  # turns integer keys into strings
		content = re.sub(r',\s+}', r'}', content)  # removes commas after the last key value pairs
		content = re.sub(r'\[(.*)\] =', r'\1:', content)  # removes brackets around keys and changes " =" to ":"
		content_dict = json.loads(content[content.find('{'):])
		return {node['dn']: node['sd'].values() for node in content_dict['nodes'].values()}


class TimelessJewelType(Enum):
	GLORIOUS_VANITY = 'glorious_vanity'
	LETHAL_PRIDE = 'lethal_pride'
	BRUTAL_RESTRAINT = 'brutal_restraint'
	MILITANT_FAITH = 'militant_faith'
	ELEGANT_HUBRIS = 'elegant_hubris'


def timeless_node_mapping(seed: int, jewel_type: TimelessJewelType) -> dict:
	with zipfile.ZipFile(f'data/TimelessJewels/{jewel_type.value}.zip') as archive:
		with archive.open(f'{seed}.csv', 'r') as infile:
			alt_passives = [
				line.split(',') for line in io.TextIOWrapper(infile, 'utf-8').read().split('\n')
			]

	with open(f'data/TimelessJewels/{jewel_type.value}_passives.txt', 'r', encoding='utf8') as file:
		passives = [int(line) for line in file.read().split('\n') if line != '']

	with open('data/TimelessJewels/stats.txt', 'r', encoding='utf8') as file:
		stats = [line for line in file.read().split('\n') if line != '']

	list_of_stats = set()
	mapping: dict[int, dict] = {}
	for p, ap in zip(passives, alt_passives):
		if ap == ['']:
			continue
		mods = []
		for i in range(1, len(ap), 2):
			list_of_stats.add(stats[int(ap[i])])
			mods.append((stats[int(ap[i])], int(ap[i + 1])))
		mapping[p] = {'replaced': bool(int(ap[0])), 'mods': mods}

	with open('data/passive_skill.json', 'r', encoding='utf8') as file:
		data = json.loads(file.read())
		stat_map = {}
		for stat in list_of_stats:
			for skill in data:
				if stat in skill['ids']:
					stat_map[stat] = skill['English']
					break

	for alt_passive in mapping.values():
		resolved_mods = []
		for mod in alt_passive['mods']:
			if mod[0] not in stat_map:
				# not sure whats the problem here, but these mods dont seem to matter anyway
				continue
			for translation in stat_map[mod[0]]:
				condition = translation['condition'][0]
				if condition == {}:
					break
				max = math.inf if condition['max'] is None else condition['max']
				min = -math.inf if condition['min'] is None else condition['min']
				if max >= mod[1] >= min:
					break
			else:
				warnings.warn(f'Could not resolve mod {mod}')
				continue
			form = translation['format'][0]
			if form == 'ignore':
				resolved_mods.append(translation['string'])
			else:
				resolved_mods.append(translation['string'].format(form.replace('#', str(mod[1]))))
		alt_passive['mods'] = resolved_mods

	return mapping

if __name__ == '__main__':
	prepare_data()
