import unittest

import data
from gems import GemQualityType, parse_skills_in_item
from stats import Stats, _parse_item

gem_data, _, _ = data.load()


def create_gem(name, level, quality, quality_type: GemQualityType = GemQualityType.Superior):
	type_line = []
	if len(gem_data[name]['static']['quality_stats']) <= quality_type.value:
		return None
	if quality_type != GemQualityType.Superior:
		type_line.append(quality_type.name)
	type_line.append(name)
	type_line = ' '.join(type_line)
	return dict(
		typeLine=type_line,
		baseType=name,
		properties=[
			{'name': 'Level', 'values': [[str(level)]]},
			{'name': 'Quality', 'values': [[str(quality)]]}
		],
		support="Support" in name
	)


def create_item(mods, socketed_gems):
	return {
		'name': '',
		'inventoryId': 'BodyArmour',
		'explicitMods': mods,
		'socketedItems': socketed_gems,
	}


class TestAuras(unittest.TestCase):
	def test_auras(self):
		"""Test that all aura gems are parsed properly without resulting in errors"""
		char_stats = Stats()
		gem_level = 20
		quality = 20
		gem_list = []
		for quality_type in GemQualityType:
			for gem_name, gem in gem_data.items():
				if str(gem_level) not in gem['per_level']:
					continue
				if 'Support' not in gem_name and gem['tags'] and 'aura' in gem['tags']:
					gem = create_gem(gem_name, gem_level, quality, quality_type)
					if gem:
						gem_list.append(gem)
			item = create_item([], gem_list)
			active_skills = parse_skills_in_item(item, char_stats)
			for gem in active_skills:
				aura_text = gem.get_aura(True)
				# for line in aura_text:
				# 	print(line)


	def test_curses(self):
		"""Test that all curse gems are parsed properly without resulting in errors"""
		char_stats = Stats()
		gem_level = 20
		quality = 20
		gem_list = []
		for quality_type in GemQualityType:
			for gem_name, gem in gem_data.items():
				if str(gem_level) not in gem['per_level']:
					continue
				if 'Support' not in gem_name and gem['tags'] and 'aura' in gem['tags']:
					gem = create_gem(gem_name, gem_level, quality, quality_type)
					if gem:
						gem_list.append(gem)
			item = create_item([], gem_list)
			active_skills = parse_skills_in_item(item, char_stats)
			for gem in active_skills:
				curse_text = gem.get_curse()
				# for line in curse_text:
				# 	print(line)


	def test_supports_for_auras(self):
		char_stats = Stats()
		gem_list = [
			create_gem("Determination", 20, 20),
			create_gem("Divine Blessing Support", 20, 20),
			create_gem("Awakened Generosity Support", 5, 20),
			create_gem("Enhance Support", 3, 20),
			create_gem("Empower Support", 3, 20),
		]
		item = create_item([], gem_list)
		active_skills = parse_skills_in_item(item, char_stats)
		determination = active_skills[0]

		assert determination.level == 23  # 20 + 1 (5 Awakened Generosity) + 2 (3 Empower)
		assert determination.quality == 36  # 20 + 16 (3 Enhance)
		assert determination.aura_effect == 78  # 0 + 44 (5 Awakened Generosity) + 34 (20 20 Divine Blessing)


	def test_supports_for_curses(self):
		char_stats = Stats()
		gem_list = [
			create_gem("Despair", 20, 20),
			create_gem("Blasphemy Support", 20, 20),
			create_gem("Arrogance Support", 20, 20),
			create_gem("Enhance Support", 3, 20),
			create_gem("Empower Support", 3, 20),
		]
		item = create_item([], gem_list)
		active_skills = parse_skills_in_item(item, char_stats)
		despair = active_skills[0]
		assert despair.level == 22  # 20 + 2 (3 Empower)
		assert despair.quality == 36  # 20 + 16 (3 Enhance)
		assert despair.get_curse_effect() == 34  # 0 + 10 (20 20 Blasphemy Support) + 24 (20 20 Arrogance Support)


	def test_global_mods_from_item(self):
		char_stats = Stats()
		item = create_item(
			mods=[
				'+1 to Level of all Lightning Spell Gems',
				'+1 to Level of all Spell Gems',
				'+20% to Quality of all Skill Gems',
				'+20 to all Attributes',
				'+20 to Dexterity and Intelligence',
				'+20 to maximum Life',
				'+20 to maximum Mana',
				'10% increased Effect of your Curses',
				'10% more Effect of your Curses',
				'10% increased Despair Curse Effect',
			],
			socketed_gems=[]
		)
		_parse_item(char_stats, item)
		assert char_stats.flat_life == 20
		assert char_stats.flat_mana == 20
		assert char_stats.flat_str == 20
		assert char_stats.flat_dex == 40
		assert char_stats.flat_int == 40
		assert char_stats.global_gem_level_increase == [({'lightning'}, 1), (set(), 1)]
		assert char_stats.global_gem_quality_increase == [(set(), 20)]
		assert char_stats.specific_curse_effect["Despair"] == 10
		assert char_stats.inc_curse_effect == 10
		assert char_stats.more_curse_effect == 10


	def test_local_mods_from_item(self):
		char_stats = Stats()
		item = create_item(
			mods=[
				'+2 to Level of Socketed Curse Gems',
				'+2 to Level of Socketed Melee Gems',
				'+1 to Level of Socketed Gems',
				'+20% to Quality of Socketed Hex Gems',
				'Socketed Gems are Supported by Level 20 Blasphemy',
				'Grants Level 20 Conductivity Skill',
				'Curse Enemies with Vulnerability on Hit with 48% increased Effect'
			],
			socketed_gems=[create_gem("Despair", 20, 20)]
		)
		active_skills = parse_skills_in_item(item, char_stats)
		assert len(active_skills) == 3
		despair = active_skills[0]
		assert despair.level == 23
		assert despair.quality == 40
		assert despair.supports
		blasphemy = despair.supports[0]
		assert blasphemy.level == 20
		assert blasphemy.quality == 0
		conductivity = active_skills[1]
		assert conductivity.level == 20
		assert conductivity.quality == 0
		assert not conductivity.supports
		vulnerability = active_skills[2]
		assert vulnerability.level == 1
		assert vulnerability.quality == 0
		assert not vulnerability.supports
		assert vulnerability.get_curse_effect() == 48
