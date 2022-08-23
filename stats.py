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

def fetch_stats(account, character_name) -> tuple[Stats, dict]:
	client = httpx.Client(timeout=15)
	client.headers['User-Agent'] = 'Mozilla/5.0'
	params = {'accountName': account, 'character': character_name, 'realm': 'pc'}
	r = client.post('https://www.pathofexile.com/character-window/get-items', data=params)
	r.raise_for_status()
	character = r.json()

	r = client.get('https://www.pathofexile.com/character-window/get-passive-skills', params=params)
	r.raise_for_status()
	skills = r.json()

	tree, masteries = _passive_skill_tree(client)

	stats = Stats(flat_life=38 + character['character']['level'] * 12,
		increased_life=0,
		strength=20,
		aura_effect=0)

	for item in character['items']:
		if item['inventoryId'] in ['Weapon2', 'Offhand2']:
			continue
		_parse_item(stats, item)
	for item in skills['items']: # jewels
		_parse_item(stats, item)
	for node_stats in iter_passives(tree, masteries, skills):
		_parse_mods(stats, node_stats)

	stats.flat_life += stats.strength // 2
	return stats, character

def iter_passives(tree, masteries, skills):
	for h in skills['hashes']:
		node = tree['nodes'][str(h)]
		yield node['stats']

	cluster_jewel_nodes = {}
	for jewel in skills['jewel_data'].values():
		if 'subgraph' in jewel:
			cluster_jewel_nodes.update(jewel['subgraph']['nodes'])
	for h in skills['hashes_ex']:
		node = cluster_jewel_nodes[str(h)]
		yield node['stats']

	for mastery_effect in skills['mastery_effects']:
		node_stats = masteries[int(mastery_effect) >> 16]
		yield node_stats

tree_dict = masteries_dict = None
def _passive_skill_tree(client) -> tuple[dict, dict]:
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
			masteries_dict[effect['effect']] = effect['stats']
	return tree_dict, masteries_dict

matchers = [(re.compile(pattern), attr) for pattern, attr in [
	(r'\+(\d+) to maximum Life', 'flat_life'),
	(r'(\d+)% increased maximum Life', 'increased_life'),
	(r'\+(\d+) to (Strength.*|all Attributes)', 'strength'),
	(r'(\d+)% increased effect of Non-Curse Auras from your Skills$', 'aura_effect'),
]]

def _parse_item(stats: Stats, item: dict):
	for modlist in ['implicitMods', 'explicitMods', 'craftedMods']:
		if modlist not in item:
			continue
		_parse_mods(stats, item[modlist])

def _parse_mods(stats: Stats, mods: list) -> None:
	for mod in mods:
		for regex, attr in matchers:
			m = regex.match(mod)
			if m:
				value = int(m.group(1))
				setattr(stats, attr, getattr(stats, attr) + value)
