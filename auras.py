import re

import stats
import gems


class Auras:

	def analyze_auras(self, char_stats, char, active_skills, skills) -> tuple[list[list[str]], list[list[str]]]:
		aura_counter = []

		results = [[f'// character increased aura effect: {char_stats.aura_effect}%']]
		vaal_results = []
		for gem in active_skills:
			if gem.applies_to_allies():
				aura_counter.append(gem.aura_effect)
			if 'aura' in gem.tags and 'curse' not in gem.tags:
				results.append(gem.get_aura(get_vaal_effect=False))
				if 'vaal' in gem.tags:
					vaal_results.append(gem.get_aura(get_vaal_effect=True))

		tree, masteries = stats.passive_skill_tree()
		for node_name, _ in stats.iter_passives(tree, masteries, skills):
			if ascendancy_result := self.ascendancy_mod(aura_counter, char_stats, node_name):
				results.append(ascendancy_result)

		for item in char['items']:
			if item['inventoryId'] in ['Weapon2', 'Offhand2']:
				continue
			if item_result := self.item_aura(item, char_stats, aura_counter):
				results.append(item_result)

		return results, vaal_results

	@staticmethod
	def analyze_curses(char_stats, active_skills) -> list[list[str]]:
		curse_effect = round(((1 + char_stats.inc_curse_effect / 100) * (1 + char_stats.more_curse_effect / 100) - 1) * 100)
		results = [[f'// character increased curse effect: {curse_effect}%']]
		for gem in active_skills:
			if 'curse' in gem.tags:
				results.append(gem.get_curse())
		return results

	@staticmethod
	def ascendancy_mod(aura_counter: list[int], char_stats: stats.Stats, node_name: str) -> list[str]:
		# TODO: champion
		if node_name == 'Champion':
			return [
				'// Champion',
				'Enemies Taunted by you take 10% increased Damage',
				'Your Hits permanently Intimidate Enemies that are on Full Life',
			]
		if node_name == 'Guardian':
			return [
				'// Guardian',
				f'+{sum(int((1 + effect/100) * 1) for effect in aura_counter)}% Physical Damage Reduction',
				'While there are at least five nearby Allies, you and nearby Allies have Onslaught',
			]
		if node_name == 'Necromancer':
			return [
				'// Necromancer',
				f'{sum(int((1 + effect/100) * 2) for effect in aura_counter)}% increased Attack and Cast Speed',
			]
		if node_name == 'Unwavering Faith':
			return [
				'// Unwavering Faith',
				f'+{sum(int((1 + effect/100) * 1) for effect in aura_counter)}% Physical Damage Reduction',
				f'{sum(round((1 + effect/100) * 0.2, 1) for effect in aura_counter)}% of Life Regenerated per second',
			]
		if node_name == 'Radiant Crusade':
			return [
				'// Radiant Crusade',
				'Deal 10% more Damage',
				'While there are at least five nearby Allies, you and nearby Allies have Onslaught'
			]
		if node_name == 'Radiant Faith':
			# TODO: take unreserved mana into account
			return [
				f'// Radiant Faith ({char_stats.mana} Mana, all reserved)',
				f'{char_stats.mana // 10} additional Energy Shield'
			]
		if node_name == 'Unwavering Crusade':
			return [
				'// Unwavering Crusade',
				'20% increased Attack, Cast and Movement Speed',
				'30% increased Area of Effect',
				'Nearby Enemies are Unnerved',
				'Nearby Enemies are Intimidated',
			]
		if node_name == 'Commander of Darkness':
			return [
				'// Commander of Darkness',
				f'{sum(int((1 + effect/100) * 3) for effect in aura_counter)}% increased Attack and Cast Speed',
				'30% increased Damage',
				'+30% to Elemental Resistances',
			]
		if node_name == 'Essence Glutton':
			return [
				'// Essence Glutton',
				'For each nearby corpse, you and nearby Allies Regenerate 0.2% of Energy Shield per second, up to 2.0% per second',
				'For each nearby corpse, you and nearby Allies Regenerate 5 Mana per second, up to 50 per second',
			]
		if node_name == 'Malediction':
			return [
				'// Malediction',
				'Nearby Enemies have Malediction'
			]
		if node_name == 'Void Beacon':
			return [
				'// Void Beacon',
				'Nearby Enemies have -20% to Cold Resistance',
				'Nearby Enemies have -20% to Chaos Resistance'
			]
		return []

	@staticmethod
	def item_aura(item: dict, char_stats: stats.Stats, aura_counter: list):
		aura_string = []
		for modlist in ['implicitMods', 'explicitMods', 'craftedMods', 'fracturedMods', 'enchantMods']:
			for mod in item.get(modlist, []):
				if m := re.search(r'Nearby Allies have (|\+)(\d+)% (.*) per 100 (.*) you have', mod, re.IGNORECASE):
					# mask of the tribunal
					value = int(m.group(2)) * getattr(char_stats, m.group(4).lower(), 0) // 100
					aura_string.append(f'{m.group(1) if m.group(1) else ""}{value}% {m.group(3)}')
				elif m := re.search(r'Auras from your Skills grant (|\+)(\d+)(.*) to you and Allies', mod, re.IGNORECASE):
					# i.e. redeemer weapon mod
					value = sum(int((1 + effect / 100) * int(m.group(2))) for effect in aura_counter)
					aura_string.append(f'{m.group(1) if m.group(1) else ""}{value}{m.group(3)}')
				elif m := re.search(r"Nearby Allies' (.*)", mod, re.IGNORECASE):
					# i.e. perquil's toe, garb of the ephemeral etc.
					aura_string.append(f'Your {m.group(1)}')
				elif m := re.search(r'Hits against Nearby Enemies have (.*)', mod, re.IGNORECASE):
					# i.e. aul's uprising etc.
					aura_string.append(f'{m.group(1)} with Hits')  # doesn't get recognized by pob if not in this form

				# Generic mods
				elif 'Nearby Enemies' in mod:
					# i.e. -% res mods on helmets 'Nearby Enemies have -X% to Y Resistance'
					aura_string.append(mod)
				elif m := re.search(r'nearby allies (have|gain) (.*)', mod, re.IGNORECASE):
					# i.e. leer cast, dying breath etc.
					# TODO: crown of the tyrant
					aura_string.append(m.group(2))
		if aura_string:
			aura_string = [f'// {item["name"]} {item["typeLine"]}'] + aura_string
		return aura_string


if __name__ == '__main__':
	character_stats, character, allocated_passives = stats.fetch_stats('raylu', 'auraraylu')
	skill_gems = [gems.parse_skills_in_item(item, character_stats) for item in character['items']]
	aura_results = Auras().analyze_auras(character_stats, character, skill_gems, allocated_passives)
	print('\n\n'.join('\n'.join(ar) for result in aura_results for ar in result))
