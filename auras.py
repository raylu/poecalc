import dataclasses
import re
from typing import Union

import data
import stats

@dataclasses.dataclass
class ItemLevelMods:
	all: int = 0
	aura: int = 0
	vaal: int = 0
	non_vaal: int = 0

class Auras:
	def __init__(self) -> None:
		self.gem_data, self.text = data.load()

	def analyze(self, account: str, character_name: str) -> list[list[str]]:
		char_stats, character = stats.fetch_stats(account, character_name)

		results = []
		for gem_name, level, supports in self.iter_gems(character['items']):
			support_comment = ', '.join(f'{s} {l}' for s, l in supports)
			aura_result = [f'// {gem_name} {level} ({support_comment})']
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
				for support, support_level in supports:
					aura_effect += self.support_aura_effect(support, support_level)
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
					aura_result.append(formatted)
				elif formatted.startswith('Aura grants ') or formatted.startswith('Buff grants '):
					formatted = formatted[len('Aura grants '):]
					aura_result.append(formatted)
				elif not formatted.startswith('You and nearby Non-Minion Allies have a '):
					raise Exception('unhandled formatted line: ' + formatted)
				i += 1
			results.append(aura_result)
		return results

	def iter_gems(self, items):
		for item in items:
			if item['inventoryId'] in ['Weapon2', 'Offhand2']:
				continue
			level_mods = ItemLevelMods()
			item_supports = []
			item_skill = None
			for mod in item.get('explicitMods', []):
				if m := re.match(r'(.\d+) to Level of Socketed Gems', mod):
					level_mods.all += int(m.group(1))
				elif m := re.match(r'(.\d+) to Level of Socketed Aura Gems', mod):
					level_mods.aura += int(m.group(1))
				elif m := re.match(r'(.\d+) to Level of Socketed Vaal Gems', mod):
					level_mods.vaal += int(m.group(1))
				elif m := re.match(r'(.\d+) to Level of Socketed Non-Vaal Gems', mod):
					level_mods.non_vaal += int(m.group(1))
				elif m := re.match(r'Socketed Gems are Supported by Level (\d+) (.+)', mod):
					item_supports.append((m.group(2) + ' Support', int(m.group(1))))
				elif m := re.match(r'Grants Level (\d+) (.+) Skill', mod):
					item_skill = (m.group(2), int(m.group(1)))

			for gem in item.get('socketedItems', []):
				if gem['support']:
					continue
				name, level = self.parse_gem(gem, level_mods)
				if 'Aura' not in self.gem_data[name]['active_skill']['types']:
					continue
				supports = item_supports + list(self.iter_supports(item, gem['socket'], level_mods))
				yield name, level, supports

			if item_skill is not None:
				all_supports = [self.parse_gem(gem, level_mods) for gem in item['socketedItems'] if gem['support']]
				yield item_skill[0], item_skill[1], all_supports

	def parse_gem(self, gem: dict, level_mods: ItemLevelMods):
		name = gem['baseType']
		gem_info = self.gem_data[name]
		if 'hybrid' in gem:
			name = gem['hybrid']['baseTypeName']

		level = None
		for prop in gem['properties']:
			if prop['name'] == 'Level' and prop['type'] == 5:
				level_str: str = prop['values'][0][0]
				if level_str.endswith(' (Max)'):
					level_str = level_str[:-len(' (Max)')]
				level = int(level_str)
				break
		assert level is not None, "couldn't get level for " + gem['typeLine']

		level += level_mods.all
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

	def support_aura_effect(self, support, level) -> int:
		# TODO: handle arrogance quality
		gem_info = self.gem_data[support]
		stats = gem_info['per_level'][str(level)].get('stats', [])
		aura_effect = 0
		for i, stat in enumerate(gem_info['static']['stats']):
			if stat['id'] in ['non_curse_aura_effect_+%', 'aura_effect_+%']:
				aura_effect += stats[i]['value']
		return aura_effect

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
	print('\n\n'.join('\n'.join(ar) for ar in Auras().analyze('raylu', 'auraraylu')))
