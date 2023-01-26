import os
import unittest

import data
from gems import GemQualityType, parse_skills_in_item
from poecalc import analyzer
from stats import Stats, _parse_item

gem_data, _, _ = data.load()


def create_gem(name, level, quality, quality_type: GemQualityType = GemQualityType.Superior, socket: int = 0):
	type_line = []
	if len(gem_data[name]['static']['quality_stats']) <= quality_type.value:
		return None
	if quality_type != GemQualityType.Superior:
		type_line.append(quality_type.name)
	type_line.append(name)
	type_line = ' '.join(type_line)
	return {
		'typeLine': type_line,
		'baseType': name,
		'properties': [
			{'name': 'Level', 'values': [[str(level)]]},
			{'name': 'Quality', 'values': [[str(quality)]]},
		],
		'support': "Support" in name,
		'socket': socket,
	}


def create_item(mods, socketed_gems, links: list[list[int]] = None):
	if links is not None:
		sockets = []
		group_counter = 0
		for linked_sockets in links:
			for _ in linked_sockets:
				sockets.append({'group': group_counter})
			group_counter += 1
	else:
		sockets = [{'group': 0} for _ in range(6)]

	return {
		'name': '',
		'inventoryId': 'BodyArmour',
		'explicitMods': mods,
		'socketedItems': socketed_gems,
		'sockets': sockets
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
				if 'Support' not in gem_name and gem['tags'] and 'aura' in gem['tags'] and 'mine' not in gem['tags']:
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

	def test_mines(self):
		"""Test that all curse gems are parsed properly without resulting in errors"""
		char_stats = Stats()
		gem_level = 20
		quality = 20
		gem_list = []
		for quality_type in GemQualityType:
			for gem_name, gem in gem_data.items():
				if str(gem_level) not in gem['per_level']:
					continue
				if 'Support' not in gem_name and gem['tags'] and 'mine' in gem['tags']:
					gem = create_gem(gem_name, gem_level, quality, quality_type)
					if gem:
						gem_list.append(gem)
			item = create_item([], gem_list)
			active_skills = parse_skills_in_item(item, char_stats)
			for gem in active_skills:
				mine_text = gem.get_mine()
				# for line in mine_text:
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

	def test_supports_for_mines(self):
		char_stats = Stats()
		char_stats.mine_aura_effect = 26
		gem_list = [
			create_gem("Portal", 1, 0),
			create_gem("High-Impact Mine Support", 20, 20, GemQualityType.Divergent),
			create_gem("Minefield Support", 20, 20, GemQualityType.Divergent),
			create_gem("Arrogance Support", 20, 20, GemQualityType.Superior),
		]
		item = create_item([], gem_list)
		active_skills = parse_skills_in_item(item, char_stats)
		portal_mine = active_skills[0]
		assert portal_mine.aura_effect == 50  # 26 (from character) + 24 (Arrogance Support)
		assert portal_mine.mine_limit == 22  # 15 (base) + 3 (minefield) + 4 (20% divergent minefield)

		assert analyzer.analyze_mines(char_stats, active_skills)[1][1] == '66% chance to deal double Damage'  # 2 * 1.5 * 22

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
		assert despair.get_curse_effect() == -7  # (100 + 24 (20 20 Arrogance Support)) * (100 - 25) (Blasphemy Support)


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
			socketed_gems=[create_gem('Despair', 20, 20)]
		)
		active_skills = parse_skills_in_item(item, char_stats)
		despair, conductivity, vulnerability = active_skills

		assert despair.level == 23
		assert despair.quality == 40
		(blasphemy,) = despair.supports
		assert blasphemy.level == 20
		assert blasphemy.quality == 0

		assert conductivity.level == 20
		assert conductivity.quality == 0
		assert not conductivity.supports

		assert vulnerability.level == 1
		assert vulnerability.quality == 0
		assert not vulnerability.supports
		assert vulnerability.get_curse_effect() == 48

	def test_socket_links_for_supports(self):
		char_stats = Stats()
		item = create_item(
			mods=[
				'Socketed Gems are Supported by Level 4 Enhance',
				'Grants Level 23 Determination Skill',
				'Curse Enemies with Vulnerability on Hit with 48% increased Effect'
			],
			socketed_gems=[
				create_gem('Discipline', 20, 20, GemQualityType.Superior, 0),
				create_gem('Divine Blessing Support', 20, 20, GemQualityType.Superior, 1),
				create_gem('Empower Support', 3, 20, GemQualityType.Superior, 2),
				create_gem('Grace', 20, 20, GemQualityType.Superior, 3)
			],
			links=[[0, 1, 2], [3]]
		)
		discipline, grace, determination, vulnerability = parse_skills_in_item(item, char_stats)

		# supported by enhance, divine blessing and empower
		assert len(discipline.supports) == 3

		# only supported by enhance from item, since it's not linked to anything
		assert len(grace.supports) == 1

		# only supported by divine blessing - empower and enhance can only support socketed gems,
		assert len(determination.supports) == 1

		# no supports
		assert len(vulnerability.supports) == 0

	def test_data_is_present(self):
		assert os.path.exists("data")
		assert os.path.exists("data/aura_skill.json")
		assert os.path.exists("data/curse_skill.json")
		assert os.path.exists("data/passive_skill.json")
		assert os.path.exists("data/gems.json")
		assert os.path.exists("data/LegionPassives.lua")
		assert os.path.exists("data/TimelessJewels.zip")
		assert os.path.exists("data/TimelessJewels")
		assert os.path.exists("data/TimelessJewels/brutal_restraint.zip")
		assert os.path.exists("data/TimelessJewels/brutal_restraint_passives.txt")
		assert os.path.exists("data/TimelessJewels/elegant_hubris.zip")
		assert os.path.exists("data/TimelessJewels/elegant_hubris_passives.txt")
		assert os.path.exists("data/TimelessJewels/glorious_vanity.zip")
		assert os.path.exists("data/TimelessJewels/glorious_vanity_passives.txt")
		assert os.path.exists("data/TimelessJewels/lethal_pride.zip")
		assert os.path.exists("data/TimelessJewels/lethal_pride_passives.txt")
		assert os.path.exists("data/TimelessJewels/militant_faith.zip")
		assert os.path.exists("data/TimelessJewels/militant_faith_passives.txt")
		assert os.path.exists("data/TimelessJewels/stats.txt")
