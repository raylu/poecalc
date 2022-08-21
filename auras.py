#!/usr/bin/env python3

import re

import data
import stats

class Auras:
	def __init__(self) -> None:
		self.gem_data = data.load()

	def analyze(self, account, character_name):
		char_stats, character = stats.fetch_stats(account, character_name)
		print(char_stats)

		for gem_name, level, supports in self.iter_gems(character['items']):
			print(gem_name, level, supports)

	def iter_gems(self, items):
		for item in items:
			aura_level_mod = 0
			item_supports = []
			for mod in item.get('explicitMods', []):
				if m := re.match(r'\+(\d+) to Level of Socketed Aura Gems', mod):
					aura_level_mod += int(m.group(1))
				elif m := re.match(r'Socketed Gems are Supported by Level (\d+) Generosity', mod):
					item_supports.append(('Generosity Support', int(m.group(1))))

			for gem in item.get('socketedItems', []):
				if gem['support']:
					continue
				name, level = self.parse_gem(gem, aura_level_mod)
				supports = item_supports + list(self.iter_supports(item, gem['socket'], aura_level_mod))
				yield name, level, supports

	def parse_gem(self, gem: dict, aura_level_mod: int):
		if 'hybrid' in gem:
			name = gem['hybrid']['baseTypeName']
		else:
			name = gem['baseType']

		level = None
		for prop in gem['properties']:
			if prop['name'] == 'Level' and prop['type'] == 5:
				level = int(prop['values'][0][0])
				break
		assert level is not None, "couldn't get level for " + gem['typeLine']

		gem_info = self.gem_data[name]
		if 'aura' in gem_info['tags']:
			level += aura_level_mod

		return name, level

	def iter_supports(self, item: dict, socket_idx: int, aura_level_mod: int):
		group = item['sockets'][socket_idx]['group']
		linked_sockets = [i for i, socket in enumerate(item['sockets']) if socket['group'] == group]
		for gem in item['socketedItems']:
			if gem['support'] and gem['socket'] in linked_sockets:
				yield self.parse_gem(gem, aura_level_mod)

if __name__ == '__main__':
	Auras().analyze('raylu', 'auraraylu')
