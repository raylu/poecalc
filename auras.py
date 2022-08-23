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
	aoe: int = 0

class Auras:
	def __init__(self) -> None:
		self.gem_data, self.text = data.load()

	def analyze(self, account: str, character_name: str) -> tuple[list[list[str]], list[list[str]]]:
		char_stats, character, skills = stats.fetch_stats(account, character_name)

		results = [[f'// character increased aura effect: {char_stats.aura_effect}%']]
		for gem_name, level, supports in self.iter_gems(character['items'], vaal=False):
			results.append(self.aura_mod(char_stats, gem_name, level, supports))

		vaal_results = []
		for gem_name, level, supports in self.iter_gems(character['items'], vaal=True):
			vaal_results.append(self.aura_mod(char_stats, gem_name, level, supports))

		num_auras = len(results) - 1
		tree, masteries = stats.passive_skill_tree()
		for node_stats in stats.iter_passives(tree, masteries, skills):
			if ascendancy_result := self.ascendancy_mod(num_auras, node_stats):
				results.append(ascendancy_result)

		return results, vaal_results

	def iter_gems(self, items, /, vaal: bool):
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
				elif m := re.match(r'(.\d+) to Level of Socketed AoE Gems', mod):
					level_mods.aoe += int(m.group(1))
				elif m := re.match(r'Socketed Gems are Supported by Level (\d+) (.+)', mod):
					item_supports.append((m.group(2) + ' Support', int(m.group(1))))
				elif m := re.match(r'Grants Level (\d+) (.+) Skill', mod):
					if vaal == m.group(2).startswith('Vaal '):
						item_skill = (m.group(2), int(m.group(1)))

			for gem in item.get('socketedItems', []):
				if gem.get('support', True): # abyss jewels don't have 'support' keys
					continue
				name, level = self.parse_gem(gem, level_mods, vaal)
				types = self.gem_data[name]['active_skill']['types']
				if 'Aura' not in types:
					continue
				if vaal != ('Vaal' in types):
					continue
				supports = item_supports + list(self.iter_supports(item, gem['socket'], level_mods))
				yield name, level, supports

			if item_skill is not None:
				all_supports = [self.parse_gem(gem, level_mods) for gem in item['socketedItems'] if gem['support']]
				yield item_skill[0], item_skill[1], all_supports

	def parse_gem(self, gem: dict, level_mods: ItemLevelMods, vaal=False):
		name = gem['baseType']
		gem_info = self.gem_data[name]
		if 'hybrid' in gem and not vaal:
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
		if 'area' in gem_info['tags']:
			level += level_mods.aoe
		if level < 1:
			# this is not the current behavior, but the current behavior is believed to be a bug
			level = 1

		return name, level

	def iter_supports(self, item: dict, socket_idx: int, level_mods: ItemLevelMods):
		group = item['sockets'][socket_idx]['group']
		linked_sockets = [i for i, socket in enumerate(item['sockets']) if socket['group'] == group]
		for gem in item['socketedItems']:
			if gem['support'] and gem['socket'] in linked_sockets:
				yield self.parse_gem(gem, level_mods)

	def aura_mod(self, char_stats: stats.Stats, gem_name: str, level: int, supports: list):
		aura_effect = char_stats.aura_effect
		for support, support_level in supports:
			aura_effect += self.support_aura_effect(support, support_level)
		support_comment = ', '.join(f'{s} {l}' for s, l in supports)
		aura_result = [f'// {gem_name} {level} ({support_comment}) {aura_effect}%']

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
			elif formatted.startswith('Aura grants ') or formatted.startswith('Buff grants '):
				formatted = formatted[len('Aura grants '):]
				aura_result.append(formatted)
			elif not formatted.startswith('You and nearby Non-Minion Allies have a '):
				raise Exception(f'unhandled formatted line from {gem_name}: {formatted}')
			i += 1

		return aura_result

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
		if allow_float:
			value = round(value, 1)
		else:
			value = int(value)
		return value

	def ascendancy_mod(self, num_auras: int, node_stats: list[str]) -> list[str]:
		# TODO: champion
		if len(node_stats) == 5 and node_stats[0] == 'Melee Hits have 50% chance to Fortify':
			return [
				'// champion',
				'Enemies Taunted by you take 10% increased Damage',
				'Your Hits permanently Intimidate Enemies that are on Full Life',
			]
		elif len(node_stats) == 5 and node_stats[0] == '25% reduced Effect of Curses on you':
			return [
				'// guardian',
				f'+{num_auras}% Physical Damage Reduction',
				'While there are at least five nearby Allies, you and nearby Allies have Onslaught',
			]
		elif len(node_stats) == 5 and node_stats[0] == 'Your Offering Skills also affect you':
			return [
				'// necromancer',
				f'{num_auras * 2}% increased Attack and Cast Speed',
			]
		elif len(node_stats) == 2 and node_stats[0] == 'Auras from your Skills grant +1% Physical Damage Reduction to you and Allies':
			return [
				'// unwavering faith',
				f'+{num_auras}% Physical Damage Reduction',
				f'{num_auras * 0.2}% of Life Regenerated per second',
			]
		elif len(node_stats) == 3 and node_stats[0] == '+20% to all Elemental Resistances':
			return ['// radiant crusade'] + node_stats[1:]
		elif len(node_stats) == 4 and node_stats[0] == 'Nearby Allies have 20% increased Attack, Cast and Movement Speed':
			return [
				'// unwavering crusade',
				'20% increased Attack, Cast and Movement Speed',
				'30% increased Area of Effect',
			]
		elif len(node_stats) == 3 and node_stats[0].startswith('Auras from your Skills grant 3% increased Attack and Cast\n'):
			return [
				'// commander of darkness',
				f'{num_auras * 3}% increased Attack and Cast Speed',
				'30% increased Damage',
				'+30% to Elemental Resistances',
			]
		elif len(node_stats) == 4 and node_stats[0].startswith('For each nearby corpse, you and nearby Allies Regenerate 0.2% of Energy Shield'):
			return [
				'// essence glutton',
				'For each nearby corpse, you and nearby Allies Regenerate 0.2% of Energy Shield per second, up to 2.0% per second',
				'For each nearby corpse, you and nearby Allies Regenerate 5 Mana per second, up to 50 per second',
			]


if __name__ == '__main__':
	print('\n\n'.join('\n'.join(ar) for result in Auras().analyze('raylu', 'auraraylu') for ar in result))
