import dataclasses
import json
import re

import httpx

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
	)

	for item in character['items']:
		if item['inventoryId'] in ['Weapon2', 'Offhand2']:
			continue
		_parse_item(stats, item)
	for item in skills['items']: # jewels
		_parse_item(stats, item)
	for notable_hash in stats.additional_notables:
		skills["hashes"].append(notable_hash)
	for _, node_stats in iter_passives(tree, masteries, skills):
		_parse_mods(stats, node_stats)

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
		yield node.get("name", ""), node['stats']

	for mastery_effect in skills['mastery_effects']:
		node = masteries[int(mastery_effect) >> 16]
		yield node['name'], node["stats"]

tree_dict = masteries_dict = None
def passive_skill_tree() -> tuple[dict, dict]:
	global tree_dict, masteries_dict
	if tree_dict is not None:
		return tree_dict, masteries_dict

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
			masteries_dict[effect['effect']] = {"name": node["name"], "stats": effect['stats']}
	return tree_dict, masteries_dict

matchers = [(re.compile(pattern), attr) for pattern, attr in [
	(r'\+(\d+) to maximum Life', 'flat_life'),
	(r'(\d+)% increased maximum Life', 'increased_life'),
	(r'\+(\d+) to (Strength.*|all Attributes)', 'strength'),
	(r'(\d+)% increased effect of Non-Curse Auras from your Skills$', 'aura_effect'),
	(r'(.*) has (\d+)% increased Aura Effect', 'specific_aura_effect'),
	(r'(.\d+) to Level of all (.*) Gems', 'global_level'),
	(r'(.\d+)% to Quality of all (.*) Gems', 'global_quality'),
	(r'Allocates (.*)', 'additional_notable')
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
				if attr == "specific_aura_effect":
					aura_name = m.group(1)
					if aura_name in stats.specific_aura_effect:
						stats.specific_aura_effect[aura_name] += int(m.group(2))
					else:
						stats.specific_aura_effect[aura_name] = int(m.group(2))
					continue

				if attr == "global_level":
					stats.global_gem_level_increase += parse_gem_descriptor(m.group(2).lower(), int(m.group(1)))
					continue

				if attr == "global_quality":
					stats.global_gem_quality_increase += parse_gem_descriptor(m.group(2).lower(), int(m.group(1)))
					continue

				if attr == "additional_notable":
					notable = m.group(1)
					if " if you have the matching modifier on" in notable:
						notable = notable.split(" if you have the matching modifier on")[0]
					stats.additional_notables |= {hash_for_notable(notable)}
					continue

				value = int(m.group(1))
				setattr(stats, attr, getattr(stats, attr) + value)

def parse_gem_descriptor(descriptor: str, value: int) -> list[tuple[list, int]]:
	if descriptor == "":
		# since active skills and supports are mutually exclusive, we can increase both if no conditions are specified
		return [(["active_skill"], value), (["support"], value)]
	if "non-" in descriptor:  # handles vaal caress - decreases all gem levels and then sets all vaal gems back to 0
		return [(["active_skill"], value), (["support"], value), ([descriptor[4:]], -value)]

	conditions = []
	if "skill" in descriptor:
		conditions.append("active_skill")
	if "aoe" in descriptor:
		conditions.append("area")
	# this list of possible tags could be fetched directly from gems.json
	for tag in ['mark', 'strength', 'duration', 'link', 'critical', 'chaos', 'nova', 'spell', 'trigger', 'bow',
				'attack', 'slam', 'warcry', 'guard', 'channelling', 'travel', 'strike', 'blessing', 'low_max_level',
				'intelligence', 'cold', 'totem', 'projectile', 'orb', 'stance', 'brand', 'dexterity', 'physical',
				'lightning', 'fire', 'aura', 'melee', 'chaining', 'herald', 'mine', 'exceptional', 'minion', 'curse', 
				'hex', 'movement', 'vaal', 'support', 'banner', 'golem', 'trap', 'blink', 'random_element', 'arcane']:
		if tag in descriptor:
			conditions.append(tag)
	return [(conditions, value)]

def hash_for_notable(notable: str) -> str:
	global tree_dict
	for hash, node in tree_dict["nodes"].items():
		if hash == "root":
			continue
		if node["name"] == notable:
			return hash
	raise FileNotFoundError(f'Notable "{notable}" could not be found in tree')
