import os
import unittest
import warnings
from typing import Optional

import data
from auras import Auras
from gems import GemQualityType, parse_skills_in_item
from stats import Stats, _parse_item, stats_for_character

gem_data, _, _ = data.load()


def gem_can_have_alt_quality(name: str, quality_type: GemQualityType) -> bool:
	return len(gem_data[name]['static']['quality_stats']) > quality_type.value


def create_gem(name: str, level: int, quality: int,
			quality_type: GemQualityType = GemQualityType.Superior, socket: int = 0) -> dict:
	type_line_list = []
	if quality_type != GemQualityType.Superior:
		type_line_list.append(quality_type.name)
	type_line_list.append(name)
	type_line = ' '.join(type_line_list)
	return {
		'typeLine': type_line,
		'baseType': name,
		'properties': [
			{'name': 'Level', 'values': [[str(level)]]},
			{'name': 'Quality', 'values': [[str(quality)]]},
		],
		'support': 'Support' in name,
		'socket': socket,
	}


def create_item(mods: list[str], socketed_gems: list[dict], links: Optional[list[list[int]]] = None) -> dict:
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
		'sockets': sockets,
	}


class TestAuras(unittest.TestCase):
	def test_auras(self) -> None:
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
					if gem_can_have_alt_quality(gem_name, quality_type):
						gem_item = create_gem(gem_name, gem_level, quality, quality_type)
						gem_list.append(gem_item)
			item = create_item([], gem_list)
			active_skills = parse_skills_in_item(item, char_stats)
			for skill_gem in active_skills:
				skill_gem.get_aura(True)

	def test_curses(self) -> None:
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
					if gem_can_have_alt_quality(gem_name, quality_type):
						gem_item = create_gem(gem_name, gem_level, quality, quality_type)
						gem_list.append(gem_item)
			item = create_item([], gem_list)
			active_skills = parse_skills_in_item(item, char_stats)
			for skill_gem in active_skills:
				skill_gem.get_curse()

	def test_mines(self) -> None:
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
					if gem_can_have_alt_quality(gem_name, quality_type):
						gem_item = create_gem(gem_name, gem_level, quality, quality_type)
						gem_list.append(gem_item)
			item = create_item([], gem_list)
			active_skills = parse_skills_in_item(item, char_stats)
			for skill_gem in active_skills:
				skill_gem.get_mine()

	def test_precision(self):
		gem_data = create_gem('Precision', 20, 0)
		(precision,) = parse_skills_in_item(create_item([], [gem_data]), Stats())
		effects = precision.get_aura(False)
		assert effects == [
			'// Precision (lvl 20, 0%)  0%',
			'+701 to Accuracy Rating', # special formatting rule from local_accuracy_rating
			'58% increased Critical Strike Chance',
		]

	def test_supports_for_auras(self) -> None:
		char_stats = Stats()
		gem_list = [
			create_gem('Determination', 20, 20),
			create_gem('Divine Blessing Support', 20, 20),
			create_gem('Awakened Generosity Support', 5, 20),
			create_gem('Enhance Support', 3, 20),
			create_gem('Empower Support', 3, 20),
		]
		item = create_item([], gem_list)
		active_skills = parse_skills_in_item(item, char_stats)
		determination = active_skills[0]

		assert determination.level == 23  # 20 + 1 (5 Awakened Generosity) + 2 (3 Empower)
		assert determination.quality == 36  # 20 + 16 (3 Enhance)
		assert determination.aura_effect == 78  # 0 + 44 (5 Awakened Generosity) + 34 (20 20 Divine Blessing)

	def test_supports_for_mines(self) -> None:
		char_stats = Stats()
		char_stats.mine_aura_effect = 26
		gem_list = [
			create_gem('Portal', 1, 0),
			create_gem('High-Impact Mine Support', 20, 20, GemQualityType.Divergent),
			create_gem('Minefield Support', 20, 20, GemQualityType.Divergent),
			create_gem('Arrogance Support', 20, 20, GemQualityType.Superior),
		]
		item = create_item([], gem_list)
		active_skills = parse_skills_in_item(item, char_stats)
		portal_mine = active_skills[0]
		assert portal_mine.aura_effect == 50  # 26 (from character) + 24 (Arrogance Support)
		assert portal_mine.mine_limit == 22  # 15 (base) + 3 (minefield) + 4 (20% divergent minefield)

		# 2 * 1.5 * 22 = 66
		assert Auras().analyze_mines(char_stats, active_skills)[1][1] == '66% chance to deal double Damage'

	def test_supports_for_curses(self) -> None:
		char_stats = Stats()
		gem_list = [
			create_gem('Despair', 20, 20),
			create_gem('Blasphemy Support', 20, 20),
			create_gem('Arrogance Support', 20, 20),
			create_gem('Enhance Support', 3, 20),
			create_gem('Empower Support', 3, 20),
		]
		item = create_item([], gem_list)
		active_skills = parse_skills_in_item(item, char_stats)
		despair = active_skills[0]
		assert despair.level == 22  # 20 + 2 (3 Empower)
		assert despair.quality == 36  # 20 + 16 (3 Enhance)
		assert despair.get_curse_effect() == -7  # (100 + 24 (20 20 Arrogance Support)) * (100 - 25) (Blasphemy Support)

	def test_global_mods_rom_item(self) -> None:
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
			socketed_gems=[],
		)
		_parse_item(char_stats, item, {})
		assert char_stats.flat_life == 20
		assert char_stats.flat_mana == 20
		assert char_stats.flat_str == 20
		assert char_stats.flat_dex == 40
		assert char_stats.flat_int == 40
		assert char_stats.global_gem_level_increase == [({'lightning'}, 1), (set(), 1)]
		assert char_stats.global_gem_quality_increase == [(set(), 20)]
		assert char_stats.specific_curse_effect['Despair'] == 10
		assert char_stats.inc_curse_effect == 10
		assert char_stats.more_curse_effect == 10

	def test_local_mods_from_item(self) -> None:
		char_stats = Stats()
		item = create_item(
			mods=[
				'+2 to Level of Socketed Curse Gems',
				'+2 to Level of Socketed Melee Gems',
				'+1 to Level of Socketed Gems',
				'+20% to Quality of Socketed Hex Gems',
				'Socketed Gems are Supported by Level 20 Blasphemy',
				'Grants Level 20 Conductivity Skill',
				'Curse Enemies with Vulnerability on Hit with 48% increased Effect',
			],
			socketed_gems=[create_gem('Despair', 20, 20)],
		)
		# pylint: disable=unbalanced-tuple-unpacking
		despair, conductivity, vulnerability = parse_skills_in_item(item, char_stats)

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

	def test_socket_links_for_supports(self) -> None:
		char_stats = Stats()
		item = create_item(
			mods=[
				'Socketed Gems are Supported by Level 4 Enhance',
				'Grants Level 23 Determination Skill',
				'Curse Enemies with Vulnerability on Hit with 48% increased Effect',
			],
			socketed_gems=[
				create_gem('Discipline', 20, 20, GemQualityType.Superior, 0),
				create_gem('Divine Blessing Support', 20, 20, GemQualityType.Superior, 1),
				create_gem('Empower Support', 3, 20, GemQualityType.Superior, 2),
				create_gem('Grace', 20, 20, GemQualityType.Superior, 3),
			],
			links=[[0, 1, 2], [3]],
		)
		# pylint: disable=unbalanced-tuple-unpacking
		discipline, grace, determination, vulnerability = parse_skills_in_item(item, char_stats)

		# supported by enhance, divine blessing and empower
		assert len(discipline.supports) == 3

		# only supported by enhance from item, since it's not linked to anything
		assert len(grace.supports) == 1

		# only supported by divine blessing - empower and enhance can only support socketed gems,
		assert len(determination.supports) == 1

		# no supports
		assert len(vulnerability.supports) == 0

	def test_link_mods(self) -> None:
		character = {
			'character': {'class': 'Scion', 'level': 100},
			'items': [],
		}
		skills = {
			'hashes': [
				60781,  # Inspiring Bond (Link Skills have 20% increased Buff Effect)
			],
			'mastery_effects': {
				'': 26985,  # Exposure near linked Targets
			},
			'items': [],
			'jewel_data': {},
			'hashes_ex': [],
		}
		stats, character, skills = stats_for_character(character, skills)
		assert stats.inc_link_effect == 20
		assert stats.link_exposure is True

	def test_link_skills(self) -> None:
		gem_list = [
			create_gem('Intuitive Link', 20, 20),
			create_gem('Vampiric Link', 20, 20),
			create_gem('Destructive Link', 20, 20),
			create_gem('Soul Link', 20, 20),
			create_gem('Flame Link', 20, 20),
			create_gem('Protective Link', 20, 20),
		]
		item = create_item(
			mods=[],
			socketed_gems=gem_list,
		)
		char_stats = Stats(
			inc_link_effect=20,
			link_exposure=True,
			life=2000,
		)
		link_skills = parse_skills_in_item(item, char_stats)
		with warnings.catch_warnings(record=True) as warning_list:
			result_array = Auras().analyze_links(char_stats, link_skills)
			assert string_in_result_array('to Critical Strike Multiplier', result_array)
			assert string_in_result_array('less damage taken from Hits', result_array)
			assert string_in_result_array('Added Fire Damage', result_array)
			assert string_in_result_array('Life when you Block', result_array)
			assert string_in_result_array('Nearby Enemies have', result_array)
			assert len(warning_list) == 2

	def test_data_is_present(self) -> None:
		assert os.path.exists('data')
		assert os.path.exists('data/aura_skill.json')
		assert os.path.exists('data/curse_skill.json')
		assert os.path.exists('data/passive_skill.json')
		assert os.path.exists('data/buff_skill.json')
		assert os.path.exists('data/skill_tree.json')
		assert os.path.exists('data/gems.json')
		assert os.path.exists('data/LegionPassives.lua')
		assert os.path.exists('data/TimelessJewels.zip')
		assert os.path.exists('data/TimelessJewels')
		assert os.path.exists('data/TimelessJewels/brutal_restraint.zip')
		assert os.path.exists('data/TimelessJewels/brutal_restraint_passives.txt')
		assert os.path.exists('data/TimelessJewels/elegant_hubris.zip')
		assert os.path.exists('data/TimelessJewels/elegant_hubris_passives.txt')
		assert os.path.exists('data/TimelessJewels/glorious_vanity.zip')
		assert os.path.exists('data/TimelessJewels/glorious_vanity_passives.txt')
		assert os.path.exists('data/TimelessJewels/lethal_pride.zip')
		assert os.path.exists('data/TimelessJewels/lethal_pride_passives.txt')
		assert os.path.exists('data/TimelessJewels/militant_faith.zip')
		assert os.path.exists('data/TimelessJewels/militant_faith_passives.txt')
		assert os.path.exists('data/TimelessJewels/stats.txt')

	def test_old_version_passives(self) -> None:
		character = {
			'character': {'class': 'Ascendant', 'level': 50},
			'items': [],
		}
		skills = {
			'hashes': [
				14674,  # Faster Doom Gain; removed in 3.20
			],
			'mastery_effects': {},
			'items': [],
			'jewel_data': {},
			'hashes_ex': [],
		}
		with warnings.catch_warnings(record=True):
			stats_for_character(character, skills)  # just test that there's no exception


def string_in_result_array(string: str, result_array: list[list[str]]):
	for subarray in result_array:
		for line in subarray:
			if string in line:
				return True
	return False
