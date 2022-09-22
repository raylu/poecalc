from dataclasses import dataclass, field
import json
import re
from collections import defaultdict
from copy import deepcopy

import httpx
import gems
import jewels


@dataclass
class Stats:
	flat_life: int = 0
	flat_str: int = 0
	flat_dex: int = 0
	flat_int: int = 0
	strength: int = 0
	dexterity: int = 0
	intelligence: int = 0
	specific_aura_effect: defaultdict[int] = field(default_factory=lambda: defaultdict(int))
	specific_curse_effect: defaultdict[int] = field(default_factory=lambda: defaultdict(int))
	increased_life: int = 0
	mana: int = 0
	flat_mana: int = 0
	inc_str: int = 0
	inc_dex: int = 0
	inc_int: int = 0
	inc_mana: int = 0
	aura_effect: int = 0
	inc_curse_effect: int = 0
	more_curse_effect: int = 0
	additional_notables: set[str] = field(default_factory=set)
	global_gem_level_increase: list[tuple[set, int]] = field(default_factory=list)
	global_gem_quality_increase: list[tuple[set, int]] = field(default_factory=list)
	devotion: int = 0
	militant_faith_aura_effect: bool = False


client = httpx.Client(timeout=15)
client.headers['User-Agent'] = 'Mozilla/5.0'


def fetch_stats(account, character_name) -> tuple[Stats, dict, dict]:
	params = {'accountName': account, 'character': character_name, 'realm': 'pc'}
	r = client.post('https://www.pathofexile.com/character-window/get-items', data=params)
	r.raise_for_status()
	character = r.json()

	r = client.get('https://www.pathofexile.com/character-window/get-passive-skills', params=params)
	r.raise_for_status()
	skills = r.json()

	tree, masteries = passive_skill_tree()

	stats = Stats(
		flat_life=38 + character['character']['level'] * 12,
		flat_str=tree['classes'][character['character']['classId']]['base_str'],
		flat_dex=tree['classes'][character['character']['classId']]['base_dex'],
		flat_int=tree['classes'][character['character']['classId']]['base_int'],
		flat_mana=34 + character['character']['level'] * 6,
	)
	tree, skills, stats = jewels.process_transforming_jewels(tree, skills, stats, character)

	for item in character['items']:
		if item['inventoryId'] in ['Weapon2', 'Offhand2']:
			continue
		_parse_item(stats, item)
	for item in skills['items']:  # jewels
		if 'Cluster Jewel' in item['typeLine']:  # skip cluster jewel base node
			continue
		_parse_item(stats, item)
	for notable_hash in stats.additional_notables:
		skills['hashes'].append(notable_hash)
	for _, node_stats in iter_passives(tree, masteries, skills):
		_parse_mods(stats, node_stats)

	if stats.militant_faith_aura_effect:
		stats.aura_effect += stats.devotion // 10
	# fun fact: this seems to be the only time when the game actually rounds to the nearest integer instead of down
	stats.strength = round(stats.flat_str * (1 + stats.inc_str / 100))
	stats.intelligence = round(stats.flat_int * (1 + stats.inc_int / 100))
	stats.dexterity = round(stats.flat_dex * (1 + stats.inc_dex / 100))
	stats.flat_life += stats.strength // 2
	stats.mana = round((stats.flat_mana + stats.intelligence // 2) * (1 + stats.inc_mana / 100))
	return stats, character, skills


def iter_passives(tree, masteries, skills):
	for h in skills['hashes']:
		node = tree['nodes'][str(h)]
		yield node['name'], node['stats']

	cluster_jewel_nodes = {}
	for jewel in skills['jewel_data'].values():
		if 'subgraph' in jewel:
			cluster_jewel_nodes.update(jewel['subgraph']['nodes'])
	for h in skills['hashes_ex']:
		node = cluster_jewel_nodes[str(h)]
		yield node.get('name', ''), node['stats']

	for mastery_effect in skills['mastery_effects']:
		node = masteries[int(mastery_effect) >> 16]
		yield node['name'], node['stats']


tree_dict = masteries_dict = None


def passive_skill_tree() -> tuple[dict, dict]:
	global tree_dict, masteries_dict
	if tree_dict is not None:
		# deepcopy to prevent modifications to the original dictionary
		return deepcopy(tree_dict), masteries_dict

	r = client.get('https://www.pathofexile.com/passive-skill-tree')
	r.raise_for_status()
	tree = r.text[r.text.index('passiveSkillTreeData'):]
	tree = tree[tree.index('{'):]
	tree = tree[:tree.index('};') + 1]
	tree_dict = json.loads(tree)

	masteries_dict = {}
	for node in tree_dict['nodes'].values():
		if 'masteryEffects' not in node:
			continue
		for effect in node['masteryEffects']:
			masteries_dict[effect['effect']] = {'name': node['name'], 'stats': effect['stats']}
	return deepcopy(tree_dict), masteries_dict


matchers = [(re.compile(pattern), attr) for pattern, attr in [
	(r'\+(\d+) to maximum Life', 'flat_life'),
	(r'(\d+)% increased maximum Life', 'increased_life'),
	(r'(.\d+) to (Strength|.+and Strength|all Attributes)', 'flat_str'),
	(r'(.\d+) to (Dexterity|.+and Dexterity|all Attributes)', 'flat_dex'),
	(r'(.\d+) to (Intelligence|.+and Intelligence|all Attributes)', 'flat_int'),
	(r'^(.\d+) to [Mm]aximum Mana', 'flat_mana'),
	(r'(\d+)% increased (Strength|Attributes)', 'inc_str'),
	(r'(\d+)% increased (Dexterity|Attributes)', 'inc_dex'),
	(r'(\d+)% increased (Intelligence|Attributes)', 'inc_int'),
	(r'(\d+)% increased maximum Mana$', 'inc_mana'),
	(r'(\d+)% increased effect of Non-Curse Auras from your Skills$', 'aura_effect'),
	(r'(.*) has (\d+)% increased Aura Effect', 'specific_aura_effect'),
	(r'(.\d+) to Level of all (.*) Gems', 'global_level'),
	(r'(.\d+)% to Quality of all (.*) Gems', 'global_quality'),
	(r'Allocates (.*)', 'additional_notable'),
	(r'(.\d+) to Devotion', 'devotion'),
	(r'Grants (.*) per (\d+)% Quality', 'alt_quality_bonus'),
	(r'(\d+)% (in|de)creased Effect of your Curses', 'inc_curse_effect'),
	(r'(\d+)% (more|less) Effect of your Curses', 'more_curse_effect'),
	(r'(\d+)% increased (.*) Curse Effect', 'specific_curse_effect')
]]


def _parse_item(stats: Stats, item: dict):
	_parse_mods(stats, jewels.process_abyss_jewels(item))
	for modlist in ['implicitMods', 'explicitMods', 'craftedMods', 'fracturedMods', 'enchantMods']:
		if modlist not in item:
			continue
		_parse_mods(stats, item[modlist])


def _parse_mods(stats: Stats, mods: list) -> None:
	for mod in mods:
		for regex, attr in matchers:
			m = regex.search(mod)
			if m:
				if attr == 'specific_aura_effect':
					stats.specific_aura_effect[m.group(1)] += int(m.group(2))
					continue

				if attr == 'global_level':
					stats.global_gem_level_increase += gems.parse_gem_descriptor(m.group(2), int(m.group(1)))
					continue

				if attr == 'global_quality':
					stats.global_gem_quality_increase += gems.parse_gem_descriptor(m.group(2), int(m.group(1)))
					continue

				if attr == 'additional_notable':
					notable = m.group(1)
					if ' if you have the matching modifier on' in notable:
						notable = notable.split(' if you have the matching modifier on')[0]
					stats.additional_notables |= {hash_for_notable(notable)}
					continue

				if attr == 'alt_quality_bonus':
					# TODO: handle quality % on item
					_parse_mods(stats, [jewels.scale_numbers_in_string(m.group(1), 20 // int(m.group(2)))])
					continue

				if attr == 'inc_curse_effect':
					if m.group(2) == 'in':
						stats.inc_curse_effect += int(m.group(1))
					else:
						stats.inc_curse_effect -= int(m.group(1))
					continue

				if attr == 'more_curse_effect':
					if m.group(2) == 'more':
						stats.more_curse_effect += int(m.group(1))
					else:
						stats.more_curse_effect -= int(m.group(1))
					continue

				if attr == 'specific_curse_effect':
					stats.specific_curse_effect[m.group(2)] += int(m.group(1))
					continue

				value = int(m.group(1))
				setattr(stats, attr, getattr(stats, attr) + value)


def hash_for_notable(notable: str) -> str:
	for hash, node in tree_dict['nodes'].items():
		if hash == 'root':
			continue
		if node['name'] == notable:
			return hash
	raise FileNotFoundError(f'Notable "{notable}" could not be found in tree')
