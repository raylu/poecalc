import dataclasses
import json
import math
import re
from copy import deepcopy

import httpx
import data

@dataclasses.dataclass
class Stats:
	flat_life: int
	increased_life: int
	strength: int
	aura_effect: int
	additional_notables: set
	global_gem_level_increase: list
	global_gem_quality_increase: list
	specific_aura_effect: dict
	devotion: int

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
		increased_life=0,
		strength=20,
		aura_effect=0,
		additional_notables=set(),
		global_gem_level_increase=[],
		global_gem_quality_increase=[],
		specific_aura_effect={},
		devotion=0
	)
	# timeless jewels have to be processed first, since conquered passives can't be modified further
	militant_faith_aura_effect = False
	for jewel in skills['items']:
		if jewel['name'] == 'Militant Faith':
			tree = process_militant_faith(jewel, tree)
			militant_faith_aura_effect = '1% increased effect of Non-Curse Auras per 10 Devotion' in jewel['explicitMods']
		elif jewel['name'] == 'Elegant Hubris':
			tree = process_elegant_hubris(jewel, tree)

	for jewel in skills['items']:
		if jewel['name'] == 'Unnatural Instinct':
			tree, skills['hashes'] = process_unnatural_instinct(jewel, tree, skills['hashes'])

	for item in character['items']:
		if item['inventoryId'] in ['Weapon2', 'Offhand2']:
			continue
		_parse_item(stats, item)
	for item in skills['items']: # jewels
		_parse_item(stats, item)
	for notable_hash in stats.additional_notables:
		skills['hashes'].append(notable_hash)
	for _, node_stats in iter_passives(tree, masteries, skills):
		_parse_mods(stats, node_stats)

	if militant_faith_aura_effect:
		stats.aura_effect += int(stats.devotion/10)
	stats.flat_life += stats.strength // 2
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
legion_passive_effects = data.legion_passive_mapping()
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
	(r'\+(\d+) to (Strength.*|all Attributes)', 'strength'),
	(r'(\d+)% increased effect of Non-Curse Auras from your Skills$', 'aura_effect'),
	(r'(.*) has (\d+)% increased Aura Effect', 'specific_aura_effect'),
	(r'(.\d+) to Level of all (.*) Gems', 'global_level'),
	(r'(.\d+)% to Quality of all (.*) Gems', 'global_quality'),
	(r'Allocates (.*)', 'additional_notable'),
	(r'(.\d+) to Devotion', 'devotion'),
]]

def _parse_item(stats: Stats, item: dict):
	for modlist in ['implicitMods', 'explicitMods', 'craftedMods', 'enchantMods']:
		if modlist not in item:
			continue
		_parse_mods(stats, item[modlist])

def _parse_mods(stats: Stats, mods: list) -> None:
	for mod in mods:
		for regex, attr in matchers:
			m = regex.search(mod)
			if m:
				if attr == 'specific_aura_effect':
					aura_name = m.group(1)
					if aura_name in stats.specific_aura_effect:
						stats.specific_aura_effect[aura_name] += int(m.group(2))
					else:
						stats.specific_aura_effect[aura_name] = int(m.group(2))
					continue

				if attr == 'global_level':
					stats.global_gem_level_increase += parse_gem_descriptor(m.group(2), int(m.group(1)))
					continue

				if attr == 'global_quality':
					stats.global_gem_quality_increase += parse_gem_descriptor(m.group(2), int(m.group(1)))
					continue

				if attr == 'additional_notable':
					notable = m.group(1)
					if ' if you have the matching modifier on' in notable:
						notable = notable.split(' if you have the matching modifier on')[0]
					stats.additional_notables |= {hash_for_notable(notable)}
					continue

				value = int(m.group(1))
				setattr(stats, attr, getattr(stats, attr) + value)

def parse_gem_descriptor(descriptor: str, value: int) -> list[tuple[list, int]]:
	descriptor = descriptor.lower()
	if descriptor == '':
		# since active skills and supports are mutually exclusive, we can increase both if no conditions are specified
		return [(['active_skill'], value), (['support'], value)]
	if 'non-' in descriptor:  # handles vaal caress - decreases all gem levels and then sets all vaal gems back to 0
		return [(['active_skill'], value), (['support'], value), ([descriptor[4:]], -value)]

	conditions = []
	if 'skill' in descriptor:
		conditions.append('active_skill')
	if 'aoe' in descriptor:
		conditions.append('area')

	all_tags = frozenset([
		'mark', 'strength', 'duration', 'link', 'critical', 'chaos', 'nova', 'spell', 'trigger', 'bow', 'attack',
		'slam', 'warcry', 'guard', 'channelling', 'travel', 'strike', 'blessing', 'low_max_level', 'intelligence',
		'cold', 'totem', 'projectile', 'orb', 'stance', 'brand', 'dexterity', 'physical', 'lightning', 'fire', 'aura',
		'melee', 'chaining', 'herald', 'mine', 'exceptional', 'minion', 'curse', 'hex', 'movement', 'vaal', 'support',
		'banner', 'golem', 'trap', 'blink', 'random_element', 'arcane'
	])
	conditions.extend(all_tags & set(descriptor.split()))
	return [(conditions, value)]

def hash_for_notable(notable: str) -> str:
	for hash, node in tree_dict['nodes'].items():
		if hash == 'root':
			continue
		if node['name'] == notable:
			return hash
	raise FileNotFoundError(f'Notable "{notable}" could not be found in tree')

def passive_node_coordinates(node: dict, tree: dict) -> (float, float):
	if 'group' not in node:
		raise ValueError(f'Cannot determine coordinates for passive node "{node}"')
	orbit_radius = tree['constants']['orbitRadii'][node['orbit']]
	n_skills = tree['constants']['skillsPerOrbit'][node['orbit']]
	group = tree['groups'][str(node['group'])]
	angle = math.pi * (2 * node['orbitIndex']/n_skills - 1/2)
	return group['x'] + orbit_radius * math.cos(angle), group['y'] + orbit_radius * math.sin(angle)

def notable_hash_for_jewel(jewel_index: int) -> str:
	return [
		'26725', '36634', '33989', '41263', '60735', '61834', '31683', '28475', '6230', '48768',
		'34483', '7960', '46882', '55190', '61419', '2491', '54127', '32763', '26196', '33631', '21984'
	][jewel_index]

def in_radius(jewel_coordinates: tuple[float, float], passive_coordinates: tuple[float, float], radius: int) -> bool:
	return (jewel_coordinates[0] - passive_coordinates[0]) ** 2 + (jewel_coordinates[1] - passive_coordinates[1]) ** 2 < radius ** 2

def nodes_in_radius(middle_passive: dict, radius: int, tree: dict) -> set[int]:
	jewel_coordinates = passive_node_coordinates(middle_passive, tree)
	passive_hashes = set()
	for node_hash, node in tree['nodes'].items():
		# exclude nodes that are not part of a group, masteries, jewel sockets or virtual class starting nodes
		if 'group' not in node or node['group'] == 0  \
				or node['name'].endswith('Mastery') \
				or node.get('isJewelSocket') \
				or node.get('classStartIndex') is not None:
			continue
		if in_radius(jewel_coordinates, passive_node_coordinates(node, tree), radius):
			passive_hashes |= {int(node_hash)}
	return passive_hashes

def process_unnatural_instinct(jewel_data: dict, tree: dict, skill_hashes: list[int]) -> tuple[dict, list]:
	jewel = tree['nodes'][notable_hash_for_jewel(jewel_data['x'])]
	for node_hash in nodes_in_radius(jewel, 960, tree):
		node = tree['nodes'][str(node_hash)]
		if node.get('isNotable') or node.get('isKeystone'):
			continue
		if node_hash not in skill_hashes:
			skill_hashes.append(node_hash)
		elif not node.get('isConquered'):  # nodes conquered by timeless jewels cant be modified
			node['stats'] = []
	return tree, skill_hashes

def process_militant_faith(jewel_data: dict, tree: dict) -> dict:
	jewel = tree['nodes'][notable_hash_for_jewel(jewel_data['x'])]
	m = re.search(r'Carved to glorify (\d+) new faithful converted by High Templar (.*)', jewel_data['explicitMods'][0])
	alt_keystone = {
		'Avarius': 'Power of Purpose',
		'Dominus': 'Inner Conviction',
		'Maxarius': 'Transcendence'
	}[m.group(2)]
	mapping = data.militant_faith_node_mapping(int(m.group(1)))
	for node_hash in nodes_in_radius(jewel, 1800, tree):
		node = tree['nodes'][str(node_hash)]
		node['isConquered'] = True
		if node.get('isNotable') and mapping[node['name']] != 'base_devotion':
			node['stats'] = legion_passive_effects[mapping[node['name']]]
		elif node.get('isKeystone'):
			node['stats'] = legion_passive_effects[alt_keystone]
		elif node['name'] in ['Intelligence', 'Strength', 'Dexterity']:
			node['stats'] = ['+10 to Devotion']
		else:
			node['stats'].append('+5 to Devotion')
	return tree

def process_elegant_hubris(jewel_data: dict, tree: dict) -> dict:
	m = re.search(r'Commissioned (\d+) coins to commemorate (.*)', jewel_data['explicitMods'][0])
	alt_keystone = {
		'Cadiro': 'Supreme Decadence',
		'Caspiro': 'Supreme Ostentation',
		'Victario': 'Supreme Grandstanding'
	}[m.group(2)]
	jewel = tree['nodes'][notable_hash_for_jewel(jewel_data['x'])]
	mapping = data.elegant_hubris_node_mapping(int(m.group(1)))
	for node_hash in nodes_in_radius(jewel, 1800, tree):
		node = tree['nodes'][str(node_hash)]
		node['isConquered'] = True
		if node.get('isNotable'):
			node['stats'] = legion_passive_effects[mapping[node['name']]]
		elif node.get('isKeystone'):
			node['stats'] = legion_passive_effects[alt_keystone]
		else:
			node['stats'] = []
	return tree
