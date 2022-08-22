#!/usr/bin/env python3

import dataclasses
import re
from typing import Union

import data
import stats

@dataclasses.dataclass
class ItemLevelMods:
	aura: int = 0
	vaal: int = 0
	non_vaal: int = 0


class Auras:
	def __init__(self) -> None:
		self.gem_data, self.text = data.load()

	def analyze(self, account, character_name):
		char_stats, character = stats.fetch_stats(account, character_name)

		for gem_name, level, supports in self.iter_gems(character['items']):
			print('//', gem_name, level, supports)
			gem_info = self.gem_data[gem_name]
			stat_values = gem_info['per_level'][str(level)]['stats']
			gem_stats = gem_info['static']['stats']
			i = 0
			while i < len(gem_stats):
				stat = gem_stats[i]
				text = self.text.get(stat['id'])
				if text is None:
					i += 1
					continue
				try:
					value = stat['value']
				except KeyError:
					value = stat_values[i]['value']

				aura_effect = char_stats.aura_effect
				value = self.scaled_value(value, aura_effect, text['index_handlers'][0])

				try:
					formatted = text['string'].format(value)
				except IndexError: # 2 mod stat
					value2 = self.scaled_value(stat_values[i+1]['value'], aura_effect, text['index_handlers'][1])
					formatted = text['string'].format(value, value2)
					i += 1
				if formatted.casefold().startswith('you and nearby allies '):
					formatted = formatted[len('you and nearby allies '):]
					if any(formatted.startswith(prefix + ' ') for prefix in ['deal', 'have', 'gain']):
						formatted = formatted[5:]
					elif not formatted.startswith('Regenerate '):
						raise Exception('unhandled formatted line: ' + formatted)
					print(formatted)
				elif not formatted.startswith('You and nearby Non-Minion Allies have a '):
					raise Exception('unhandled formatted line: ' + formatted)
				i += 1
			print()

	def iter_gems(self, items):
		for item in items:
			level_mods = ItemLevelMods()
			item_supports = []
			for mod in item.get('explicitMods', []):
				if m := re.match(r'(.\d+) to Level of Socketed Aura Gems', mod):
					level_mods.aura += int(m.group(1))
				elif m := re.match(r'(.\d+) to Level of Socketed Vaal Gems', mod):
					level_mods.vaal += int(m.group(1))
				elif m := re.match(r'(.\d+) to Level of Socketed Non-Vaal Gems', mod):
					level_mods.non_vaal += int(m.group(1))
				elif m := re.match(r'Socketed Gems are Supported by Level (\d+) Generosity', mod):
					item_supports.append(('Generosity Support', int(m.group(1))))

			for gem in item.get('socketedItems', []):
				if gem['support']:
					continue
				name, level = self.parse_gem(gem, level_mods)
				supports = item_supports + list(self.iter_supports(item, gem['socket'], level_mods))
				yield name, level, supports

	def parse_gem(self, gem: dict, level_mods: ItemLevelMods):
		name = gem['baseType']
		gem_info = self.gem_data[name]
		if 'hybrid' in gem:
			name = gem['hybrid']['baseTypeName']

		level = None
		for prop in gem['properties']:
			if prop['name'] == 'Level' and prop['type'] == 5:
				level = int(prop['values'][0][0])
				break
		assert level is not None, "couldn't get level for " + gem['typeLine']

		if 'aura' in gem_info['tags']:
			level += level_mods.aura
		if 'vaal' in gem_info['tags']:
			level += level_mods.vaal
		else:
			level += level_mods.non_vaal

		return name, level

	def iter_supports(self, item: dict, socket_idx: int, level_mods: ItemLevelMods):
		group = item['sockets'][socket_idx]['group']
		linked_sockets = [i for i, socket in enumerate(item['sockets']) if socket['group'] == group]
		for gem in item['socketedItems']:
			if gem['support'] and gem['socket'] in linked_sockets:
				yield self.parse_gem(gem, level_mods)

	def scaled_value(self, value: int, aura_effect: int, index_handlers: list[str]) -> Union[int, float]:
		allow_float = False
		for handler in index_handlers:
			if handler == 'per_minute_to_per_second':
				value /= 60
				allow_float = True
			else:
				raise Exception('unhandled index_handler: ' + handler)
		value *= 1 + aura_effect / 100
		if not allow_float:
			value = int(value)
		return value

if __name__ == '__main__':
	Auras().analyze('raylu', 'auraraylu')
