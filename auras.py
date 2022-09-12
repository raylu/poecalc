import re
from copy import copy, deepcopy
from enum import Enum
from typing import Union

import data
import stats

class GemQualityType(Enum):
	Superior = 0
	Anomalous = 1
	Divergent = 2
	Phantasmal = 3


class Auras:
	def __init__(self) -> None:
		self.gem_data, self.text = data.load()

	def analyze(self, account: str, character_name: str, user_aura_effect: int = None) -> tuple[list[list[str]], list[list[str]]]:
		char_stats, character, skills = stats.fetch_stats(account, character_name)
		if user_aura_effect is not None:
			char_stats.aura_effect = user_aura_effect
		aura_counter = []

		results = [[f'// character increased aura effect: {char_stats.aura_effect}%']]
		for gem_name, level, quality, quality_type, supports in self.iter_gems(character['items'], char_stats,  vaal=False):
			aura_result, ally_aura = self.aura_mod(char_stats, gem_name, level, quality, quality_type, supports)
			results.append(aura_result)
			aura_counter += ally_aura

		vaal_results = []
		for gem_name, level, quality, quality_type, supports in self.iter_gems(character['items'], char_stats, vaal=True):
			aura_result, ally_aura = self.aura_mod(char_stats, gem_name, level, quality, quality_type, supports)
			vaal_results.append(aura_result)
			# not sure if vaal auras should be included for the ascendancy effects
			# aura_counter += ally_aura

		tree, masteries = stats.passive_skill_tree()
		for node_name, node_stats in stats.iter_passives(tree, masteries, skills):
			if ascendancy_result := self.ascendancy_mod(aura_counter, node_name):
				results.append(ascendancy_result)

		return results, vaal_results

	def iter_gems(self, items, character_stats: stats.Stats, vaal: bool):
		for item in items:
			if item['inventoryId'] in ['Weapon2', 'Offhand2']:
				continue
			level_mods = copy(character_stats.global_gem_level_increase)
			quality_mods = copy(character_stats.global_gem_quality_increase)
			item_supports = []
			item_skill = None
			for mod_type in ['explicitMods', 'implicitMods']:
				for mod in item.get(mod_type, []):
					if m := re.search(r'(.\d+) to Level of Socketed (.*)Gems', mod):
						value = int(m.group(1))
						if not m.group(2):
							descriptor = ''
						else:
							descriptor = m.group(2)[:-1]
						level_mods += stats.parse_gem_descriptor(descriptor, value)

					elif m := re.search(r'(.\d+)% to Quality of Socketed (.*)Gems', mod):
						value = int(m.group(1))
						if not m.group(2):
							descriptor = ''
						else:
							descriptor = m.group(2)[:-1]
						quality_mods += stats.parse_gem_descriptor(descriptor, value)

					elif m := re.match(r'Socketed Gems are Supported by Level (\d+) (.+)', mod):
						item_supports.append((m.group(2) + ' Support', int(m.group(1)), 0, GemQualityType.Superior))
					elif m := re.match(r'Grants Level (\d+) (.+) Skill', mod):
						if vaal == m.group(2).startswith('Vaal '):
							item_skill = (m.group(2), int(m.group(1)), 0, GemQualityType.Superior)

			for gem in item.get('socketedItems', []):
				if gem.get('support', True): # abyss jewels don't have 'support' keys
					continue
				name, level, quality, quality_type = self.parse_gem(gem, level_mods, quality_mods, vaal)
				types = self.gem_data[name]['active_skill']['types']
				if 'Aura' not in types:
					continue
				if vaal != ('Vaal' in types):
					continue
				supports = item_supports + list(self.iter_supports(item, gem['socket'], level_mods, quality_mods))
				yield name, level, quality, quality_type, supports

			if item_skill is not None:
				all_supports = [self.parse_gem(gem, level_mods, quality_mods) for gem in item['socketedItems'] if gem['support']]
				yield item_skill[0], item_skill[1], item_skill[2], item_skill[3], all_supports

	def parse_gem(self, gem: dict, level_mods: list, quality_mods: list, vaal=False) -> (str, int, int, GemQualityType):
		name = gem['baseType']
		gem_info = self.gem_data[name]
		if 'hybrid' in gem and not vaal:
			name = gem['hybrid']['baseTypeName']

		quality_type = GemQualityType.Superior
		for i, alt_quality_type in enumerate(GemQualityType._member_names_):
			if alt_quality_type in gem['typeLine']:
				quality_type = GemQualityType(i)
				break

		level = None
		quality = 0
		for prop in gem['properties']:
			if prop['name'] == 'Level' and prop['type'] == 5:
				level_str: str = prop['values'][0][0]
				if level_str.endswith(' (Max)'):
					level_str = level_str[:-len(' (Max)')]
				level = int(level_str)
			if prop['name'] == 'Quality':
				quality = int(prop['values'][0][0][1:-1])
		assert level is not None, "couldn't get level for " + gem['typeLine']
		for tag_conditions, level_modification in level_mods:
			if all(condition in gem_info['tags'] for condition in tag_conditions):
				level += level_modification

		for tag_conditions, quality_modification in quality_mods:
			if all(condition in gem_info['tags'] for condition in tag_conditions):
				quality += quality_modification
		if level < 1:
			# this is not the current behavior, but the current behavior is believed to be a bug
			level = 1
		return name, level, quality, quality_type

	def iter_supports(self, item: dict, socket_idx: int, level_mods: list, quality_mods: list):
		group = item['sockets'][socket_idx]['group']
		linked_sockets = [i for i, socket in enumerate(item['sockets']) if socket['group'] == group]
		for gem in item['socketedItems']:
			if gem['support'] and gem['socket'] in linked_sockets:
				yield self.parse_gem(gem, level_mods, quality_mods)

	def aura_mod(self, char_stats: stats.Stats, gem_name: str, level: int, quality: int, quality_type: GemQualityType, supports: list) -> tuple[list[str], list[int]]:
		aura_effect = char_stats.aura_effect
		if gem_name in char_stats.specific_aura_effect:
			aura_effect += char_stats.specific_aura_effect[gem_name]
		gem_info = self.gem_data[gem_name]

		support_comments = []
		for support, support_level, support_quality, support_quality_type in supports:
			additional_levels, additional_quality, additional_effect = self.support_aura_effect(support, support_level, support_quality, support_quality_type, gem_info)
			aura_effect += additional_effect
			level += additional_levels
			quality += additional_quality
			if additional_levels or additional_quality or additional_effect:  # only include supports that contribute
				support_comments.append(f'{support} {support_level}')

		support_comment = ', '.join(support_comments)
		mods_from_quality, effect_from_quality = self.parse_gem_quality(gem_name, quality, quality_type)
		aura_effect += effect_from_quality
		special_quality = f'{quality_type.name} ' if quality_type != GemQualityType.Superior else ''
		aura_result = [f'// {special_quality}{gem_name} (lvl {level}, {quality}%) ({support_comment}) {aura_effect}%']

		stat_values = gem_info['per_level'][str(level)]['stats']
		gem_stats = gem_info['static']['stats'] + mods_from_quality
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

			value = self.scaled_value(value, aura_effect, text['index_handlers'][0])
			try:
				formatted = text['string'].format(value)
			except IndexError: # 2 mod stat
				value2 = self.scaled_value(stat_values[i+1]['value'], aura_effect, text['index_handlers'][1])
				formatted = text['string'].format(value, value2)
				i += 1
			if formatted.casefold().startswith('you and nearby allies '):
				formatted = formatted[len('you and nearby allies '):]
				verb, mod = formatted.split(' ', 1)
				if verb in ['deal', 'have', 'gain', 'are']:
					formatted = mod
				elif not formatted.startswith('Regenerate '):
					raise Exception(f'unhandled formatted line from {text["string"]}: {formatted}')
				aura_result.append(formatted)
			elif m := re.search("nearby allies' (.*)", formatted, re.IGNORECASE):
				aura_result.append(f'Your {m.group(1)}')
			elif formatted.startswith('Aura grants ') or formatted.startswith('Buff grants '):
				formatted = formatted[len('Aura grants '):]
				aura_result.append(formatted)
			elif not formatted.startswith('You and nearby Non-Minion Allies have a '):
				raise Exception(f'unhandled formatted line from {gem_name}: {formatted}')
			i += 1

		aura_addition = [aura_effect] if 'AuraAffectsEnemies' not in gem_info['active_skill']['types'] else []

		return aura_result, aura_addition

	def support_aura_effect(self, support, level, quality, quality_type, active_skill_info) -> (int, int, int):
		gem_info = self.gem_data[support]
		stats = gem_info['per_level'][str(level)].get('stats', [])
		aura_effect = 0
		level_increase = 0
		quality_increase = 0
		active_gem_tags = active_skill_info.get('tags', []) + active_skill_info['active_skill'].get('types', [])

		active_gem_tags_set = set(tag.lower() for tag in active_gem_tags)
		allowed_types_set = set(gem_type.lower() for gem_type in gem_info['support_gem']['allowed_types'])
		if len(active_gem_tags_set & allowed_types_set) == 0:
			return 0, 0, 0

		for i, stat in enumerate(gem_info['static']['stats']):
			if stat['id'] in ['non_curse_aura_effect_+%', 'aura_effect_+%']:
				aura_effect += stats[i]['value']
			elif stat['id'] == 'supported_aura_skill_gem_level_+':
				level_increase += stats[i]['value']
			elif stat['id'] == 'supported_active_skill_gem_quality_%':
				quality_increase += stats[i]['value']
		if quality > 0:  # arrogance / anomalous generosity
			for stat in gem_info['static']['quality_stats']:
				if stat['set'] == quality_type.value and stat['id'] in ['non_curse_aura_effect_+%', 'aura_effect_+%']:
					aura_effect += int(stat['value'] * quality/1000)
		return level_increase, quality_increase, aura_effect

	def scaled_value(self, value: int, aura_effect: int, index_handlers: list[str]) -> Union[int, float]:
		allow_float = False
		for handler in index_handlers:
			if handler == 'per_minute_to_per_second':
				value /= 60
				allow_float = True
			else:
				raise Exception('unhandled index_handler: ' + handler)
		value *= 1 + aura_effect / 100
		if allow_float:
			value = round(value, 1)
		else:
			value = int(value)
		return value

	def ascendancy_mod(self, aura_counter: list[int], node_name: str) -> list[str]:
		# TODO: champion
		if node_name == 'Champion':
			return [
				'// Champion',
				'Enemies Taunted by you take 10% increased Damage',
				'Your Hits permanently Intimidate Enemies that are on Full Life',
			]
		elif node_name == 'Guardian':
			return [
				'// Guardian',
				f'+{sum(int((1 + effect/100) * 1) for effect in aura_counter)}% Physical Damage Reduction',
				'While there are at least five nearby Allies, you and nearby Allies have Onslaught',
			]
		elif node_name == 'Necromancer':
			return [
				'// Necromancer',
				f'{sum(int((1 + effect/100) * 2) for effect in aura_counter)}% increased Attack and Cast Speed',
			]
		elif node_name == 'Unwavering Faith':
			return [
				'// Unwavering Faith',
				f'+{sum(int((1 + effect/100) * 2) for effect in aura_counter)}% Physical Damage Reduction',
				f'{sum(round((1 + effect/100 * 0.2), 1) for effect in aura_counter)}% of Life Regenerated per second',
			]
		elif node_name == 'Radiant Crusade':
			return ['// Radiant Crusade'] + ['Deal 10% more Damage']
		elif node_name == 'Unwavering Crusade':
			return [
				'// Unwavering Crusade',
				'20% increased Attack, Cast and Movement Speed',
				'30% increased Area of Effect',
			]
		elif node_name == 'Commander of Darkness':
			return [
				'// Commander of Darkness',
				f'{sum(int((1 + effect/100) * 3) for effect in aura_counter)}% increased Attack and Cast Speed',
				'30% increased Damage',
				'+30% to Elemental Resistances',
			]
		elif node_name == 'Essence Glutton':
			return [
				'// Essence Glutton',
				'For each nearby corpse, you and nearby Allies Regenerate 0.2% of Energy Shield per second, up to 2.0% per second',
				'For each nearby corpse, you and nearby Allies Regenerate 5 Mana per second, up to 50 per second',
			]

	def parse_gem_quality(self, gem_name, quality, quality_type):
		gem_info = self.gem_data[gem_name]
		additional_effects = []
		aura_effect_increase = 0
		if quality > 0:
			gem_quality_stats = deepcopy(gem_info['static']['quality_stats'])  # prevents overwriting of gem data
			for stat in gem_quality_stats:
				if stat['set'] == quality_type.value:
					stat['value'] = int(stat['value'] * quality/1000)
					if stat['id'] in self.text: # if the quality grants an additional effect

						additional_effects.append(stat)
					elif stat['id'] in ['aura_effect_+%', 'defiance_banner_aura_effect_+%', 'non_curse_aura_effect_+%']:
						aura_effect_increase += stat['value']
		return additional_effects, aura_effect_increase

if __name__ == '__main__':
	print('\n\n'.join('\n'.join(ar) for result in Auras().analyze('raylu', 'auraraylu') for ar in result))
