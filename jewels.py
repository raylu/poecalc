import math
import re
import data

legion_passive_effects = data.legion_passive_mapping()
notable_hashes_for_jewels = [
    '26725', '36634', '33989', '41263', '60735', '61834', '31683', '28475', '6230', '48768', '34483', '7960',
    '46882', '55190', '61419', '2491', '54127', '32763', '26196', '33631', '21984', '29712', '48679', '9408',
    '12613', '16218', '2311', '22994', '40400', '46393', '61305', '12161', '3109', '49080', '17219', '44169',
    '24970', '36931', '14993', '10532', '23756', '46519', '23984', '51198', '61666', '6910', '49684', '33753',
    '18436', '11150', '22748', '64583', '61288', '13170', '9797', '41876', '59585'
]


class TreeGraph:
    """This class is used to determine the shortest paths between two passive skills in a given passive tree"""
    def __init__(self, tree, skills):
        # skills['hashes'] can contain hashes that are not part of the tree (cluster notables)
        self.node_hashes = {str(hash) for hash in skills['hashes']} & \
                           set(node_hash for node_hash in tree['nodes'] if node_hash != 'root')
        self.tree = tree
        self.id_for_hash = {node: idx for idx, node in enumerate(self.node_hashes)}
        self.adjacency_list = {node: set() for node in range(len(self.node_hashes))}
        self.fill_adjacency_list()

    def fill_adjacency_list(self):
        for idx, node_hash in enumerate(self.node_hashes):
            node = self.tree['nodes'].get(node_hash)
            if node is None:
                continue
            for neighbour_hash in ((set(node.get('in', [])) | set(node.get('out', []))) & self.node_hashes):
                self.add_edge(idx, self.id_for_hash[neighbour_hash])

    def add_edge(self, node1, node2):
        self.adjacency_list[node1].add(node2)
        self.adjacency_list[node2].add(node1)

    def bfs(self, start_node_hash, target_node_hash):
        start_node = self.id_for_hash[start_node_hash]
        target_node = self.id_for_hash[target_node_hash]
        queue = [start_node]
        visited = {start_node}
        parent = dict()
        parent[start_node] = None
        path_found = False
        while queue:
            current_node = queue.pop(0)
            if current_node == target_node:
                path_found = True
                break
            for next_node in self.adjacency_list[current_node] - visited:
                queue.append(next_node)
                parent[next_node] = current_node
                visited.add(next_node)
        if not path_found:
            return math.inf

        path_length = 0
        while parent[target_node] is not None:
            path_length += 1
            target_node = parent[target_node]
        return path_length


def passive_node_coordinates(node: dict, tree: dict) -> (float, float):
    if 'group' not in node:
        raise ValueError(f'Cannot determine coordinates for passive node "{node}"')
    orbit_radius = tree['constants']['orbitRadii'][node['orbit']]
    n_skills = tree['constants']['skillsPerOrbit'][node['orbit']]
    group = tree['groups'][str(node['group'])]
    angle = math.pi * (2 * node['orbitIndex'] / n_skills - 1 / 2)
    return group['x'] + orbit_radius * math.cos(angle), group['y'] + orbit_radius * math.sin(angle)


def in_radius(jewel_coordinates: tuple[float, float], passive_coordinates: tuple[float, float], radius: int) -> bool:
    jewel_x, jewel_y = jewel_coordinates
    passive_x, passive_y = passive_coordinates
    return (jewel_x - passive_x) ** 2 + (jewel_y - passive_y) ** 2 < radius ** 2


def nodes_in_radius(middle_passive: dict, radius: int, tree: dict) -> set[int]:
    jewel_coordinates = passive_node_coordinates(middle_passive, tree)
    passive_hashes = set()
    for node_hash, node in tree['nodes'].items():
        # exclude nodes that are not part of a group, masteries, jewel sockets or virtual class starting nodes
        if 'group' not in node or node['group'] == 0 \
                or node['name'].endswith('Mastery') \
                or node.get('isJewelSocket') \
                or node.get('classStartIndex') is not None:
            continue
        if in_radius(jewel_coordinates, passive_node_coordinates(node, tree), radius):
            passive_hashes.add(int(node_hash))
    return passive_hashes


def get_radius(jewel, skills) -> int:
    return skills['jewel_data'][str(jewel['x'])]['radius']


def scale_effect(initial_value: str, scaling_factor: float) -> str:
    return str(int(int(initial_value) * scaling_factor))


def scale_numbers_in_string(string: str, scaling_factor: float) -> str:
    return re.sub(r'(\d+)', lambda x: scale_effect(x.group(1), scaling_factor), string)


def process_transforming_jewels(tree, skills, stats, character):
    jewel_priority = {
        # Timeless jewels need to be processed first, since they block other jewels from modifying notables in radius
        'Militant Faith': 1,
        'Elegant Hubris': 1,
        # To avoid rounding errors, healthy mind is processed before other jewels
        # example:
        # - '5% increased max life' -> healthy mind -> 10% -> might of the meek -> 15%
        # - '5% increased max life' -> might of the meek -> 7% -> healthy mind -> 14%
        'Healthy Mind': 2,
        # lower priority jewels
        'Split Personality': 3,
        'Might of the Meek': 3,
        # unnatural instinct needs to be processed last since it allocates, which can mess up split personality
        'Unnatural Instinct': 4,
    }
    special_jewels = [(jewel, jewel_priority[jewel['name']]) for jewel in skills['items'] if jewel['name'] in jewel_priority]
    special_jewels.sort(key=lambda x: x[1])

    for jewel, _ in special_jewels:
        if jewel['name'] == 'Militant Faith':
            tree = process_militant_faith(jewel, tree, get_radius(jewel, skills))
            stats.militant_faith_aura_effect = '1% increased effect of Non-Curse Auras per 10 Devotion' in jewel['explicitMods']
        elif jewel['name'] == 'Elegant Hubris':
            tree = process_elegant_hubris(jewel, tree, get_radius(jewel, skills))
        elif jewel['name'] == 'Healthy Mind':
            tree = process_healthy_mind(jewel, tree, get_radius(jewel, skills))
        elif jewel['name'] == 'Split Personality':
            jewel = process_split_personality(jewel, tree, skills, character)
        elif jewel['name'] == 'Might of the Meek':
            tree = process_might_of_the_meek(jewel, tree, get_radius(jewel, skills))
        elif jewel['name'] == 'Unnatural Instinct':
            tree, skills['hashes'] = process_unnatural_instinct(jewel, tree, skills['hashes'], get_radius(jewel, skills))
    return tree, skills, stats


def process_unnatural_instinct(jewel_data: dict, tree: dict, skill_hashes: list[int], radius: int) -> tuple[dict, list]:
    """
    Allocated Small Passive Skills in Radius grant nothing
    Grants all bonuses of Unallocated Small Passive Skills in Radius
    """
    jewel = tree['nodes'][notable_hashes_for_jewels[jewel_data['x']]]
    for node_hash in nodes_in_radius(jewel, radius, tree):
        node = tree['nodes'][str(node_hash)]
        if node.get('isNotable') or node.get('isKeystone'):
            continue
        if node_hash not in skill_hashes:
            skill_hashes.append(node_hash)
        elif not node.get('isConquered'):  # nodes conquered by timeless jewels cant be modified
            node['stats'] = []
    return tree, skill_hashes


def process_militant_faith(jewel_data: dict, tree: dict, radius: int) -> dict:
    jewel = tree['nodes'][notable_hashes_for_jewels[jewel_data['x']]]
    m = re.search(r'Carved to glorify (\d+) new faithful converted by High Templar (.*)', jewel_data['explicitMods'][0])
    alt_keystone = {
        'Avarius': 'Power of Purpose',
        'Dominus': 'Inner Conviction',
        'Maxarius': 'Transcendence'
    }[m.group(2)]
    mapping = data.militant_faith_node_mapping(m.group(1))
    for node_hash in nodes_in_radius(jewel, radius, tree):
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


def process_elegant_hubris(jewel_data: dict, tree: dict, radius: int) -> dict:
    m = re.search(r'Commissioned (\d+) coins to commemorate (.*)', jewel_data['explicitMods'][0])
    alt_keystone = {
        'Cadiro': 'Supreme Decadence',
        'Caspiro': 'Supreme Ostentation',
        'Victario': 'Supreme Grandstanding'
    }[m.group(2)]
    jewel = tree['nodes'][notable_hashes_for_jewels[jewel_data['x']]]
    mapping = data.elegant_hubris_node_mapping(m.group(1))
    for node_hash in nodes_in_radius(jewel, radius, tree):
        node = tree['nodes'][str(node_hash)]
        node['isConquered'] = True
        if node.get('isNotable'):
            node['stats'] = legion_passive_effects[mapping[node['name']]]
        elif node.get('isKeystone'):
            node['stats'] = legion_passive_effects[alt_keystone]
        else:
            node['stats'] = []
    return tree


def process_healthy_mind(jewel_data: dict, tree: dict, radius: int) -> dict:
    """Increases and Reductions to Life in Radius are Transformed to apply to Mana at 200% of their value"""
    jewel = tree['nodes'][notable_hashes_for_jewels[jewel_data['x']]]
    for node_hash in nodes_in_radius(jewel, radius, tree):
        node = tree['nodes'][str(node_hash)]
        if node.get('isKeystone') or node.get('isConquered'):
            continue

        node['stats'] = [
            re.sub(
                r'(\d+)% increased maximum Life',
                lambda x: f'{scale_effect(x.group(1), 2)}% increased maximum Mana',
                stat
            ) for stat in node['stats']
        ]
    return tree


def process_might_of_the_meek(jewel_data: dict, tree: dict, radius: int) -> dict:
    """
    50% increased Effect of non-Keystone Passive Skills in Radius
    Notable Passive Skills in Radius grant nothing
    """
    jewel = tree['nodes'][notable_hashes_for_jewels[jewel_data['x']]]
    for node_hash in nodes_in_radius(jewel, radius, tree):
        node = tree['nodes'][str(node_hash)]
        if node.get('isKeystone') or node.get('isConquered'):
            continue
        elif node.get('isNotable'):
            node['stats'] = []
            continue
        node['stats'] = [scale_numbers_in_string(stat, 1.5) for stat in node['stats']]
    return tree


def class_starting_nodes(tree, character, skills) -> set:
    for node in tree['nodes'].values():
        if node.get('classStartIndex') == character['character']['classId']:
            return {str(h) for h in skills['hashes']} & (set(node['in']) | set(node['out']))
    return set()


def get_cluster_root(jewel_hash, tree) -> tuple[str, int]:
    """
    Returns the hash for the root cluster jewel slot, if the jewel is in a cluster slot and its distance from it
    Assumptions:
    - Cluster Jewels have minimum amount of small passives
    - Medium Cluster Jewels are not socketed into the Large Cluster Socket
    - Large Cluster Jewels are not Voices
    """
    additional_distance = 0
    jewel = tree['nodes'][jewel_hash]
    if jewel['name'] == 'Small Jewel Socket':
        additional_distance += 3
        jewel = tree['nodes'][jewel['expansionJewel']['parent']]
    if jewel['name'] == 'Medium Jewel Socket':
        additional_distance += 3
        jewel = tree['nodes'][jewel['expansionJewel']['parent']]
    return str(jewel['skill']), additional_distance


def process_split_personality(jewel_data: dict, tree: dict, skills: dict, character):
    jewel_hash = notable_hashes_for_jewels[jewel_data['x']]
    jewel_hash, additional_distance = get_cluster_root(jewel_hash, tree)
    g = TreeGraph(tree, skills)
    minimum_distance = math.inf
    for node in class_starting_nodes(tree, character, skills):
        distance = g.bfs(node, jewel_hash)
        if distance < minimum_distance:
            minimum_distance = distance
    jewel_data['explicitMods'] = [scale_numbers_in_string(stat, 1 + 0.25 * (minimum_distance + additional_distance))
                                  for stat in jewel_data['explicitMods'][1:]]
    return jewel_data


def process_abyss_jewels(item: dict):
    mods = []
    for jewel in item.get('socketedItems', []):
        if not jewel.get('abyssJewel'):
            continue
        if item.get('name') == 'Darkness Enthroned':
            scaling = 1.75
        else:
            scaling = 1
        for mod_type in ['explicitMods', 'implicitMods', 'fracturedMods']:
            for mod in jewel.get(mod_type, []):
                mods.append(re.sub(r'(\d+)', lambda x, sc=scaling: scale_effect(x.group(), sc), mod))
    return mods
