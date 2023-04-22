import re

import gems
import stats

class Auras:

    def analyze_auras(self, char_stats: stats.Stats, char: dict, active_skills: list[gems.SkillGem], skills: dict) \
            -> tuple[list[list[str]], list[list[str]]]:
        aura_counter = []

        results = [[f'// character increased aura effect: {char_stats.aura_effect}%']]
        vaal_results = []
        for gem in active_skills:
            if gem.applies_to_allies():
                aura_counter.append(gem.aura_effect)
            if 'aura' in gem.tags and not {'curse', 'remotemined'} & gem.tags:
                results.append(gem.get_aura(get_vaal_effect=False))
                if 'vaal' in gem.tags:
                    vaal_results.append(gem.get_aura(get_vaal_effect=True))

        tree, masteries = stats.passive_skill_tree()
        for node_name, _ in stats.iter_passives(tree, masteries, skills):
            if ascendancy_result := self.ascendancy_mod(aura_counter, char_stats, node_name):
                results.append(ascendancy_result)

        for item in char['items']:
            if item_result := self.item_aura(item, char_stats, aura_counter):
                results.append(item_result)

        return results, vaal_results

    @staticmethod
    def analyze_curses(char_stats: stats.Stats, active_skills: list[gems.SkillGem]) -> list[list[str]]:
        curse_effect = round(
            ((1 + char_stats.inc_curse_effect / 100) * (1 + char_stats.more_curse_effect / 100) - 1) * 100)
        results = [[f'// character increased curse effect: {curse_effect}%']]
        for gem in active_skills:
            if 'curse' in gem.tags:
                results.append(gem.get_curse())
        if len(results) == 1:
            return []
        return results

    @staticmethod
    def analyze_mines(char_stats: stats.Stats, active_skills: list[gems.SkillGem]) -> list[list[str]]:
        effect = char_stats.aura_effect + char_stats.mine_aura_effect + char_stats.aura_effect_on_enemies
        results = [[f'// character increased aura effect for mines: {effect}%']]
        for gem in active_skills:
            if 'remotemined' in gem.tags:
                results.append(gem.get_mine())
        if len(results) == 1:
            return []
        return results

    @staticmethod
    def analyze_links(char_stats: stats.Stats, active_skills: list[gems.SkillGem]) -> list[list[str]]:
        results = [['// Effects from Link Skills:']]
        for gem in active_skills:
            if 'link' in gem.tags:
                results.append(gem.get_link())

        if len(results) == 1:
            return []
        additional_results = []
        if char_stats.link_exposure:
            additional_results.append('Nearby Enemies have -10% to Elemental Resistances')
        if additional_results:
            results.append(['// Additional Link effects', *additional_results])
        return results

    @staticmethod
    def ascendancy_mod(aura_counter: list[int], char_stats: stats.Stats, node_name: str) -> list[str]:
        ascendancies = {
            'Champion': [
                'Enemies Taunted by you take 10% increased Damage',
            ],
            'Guardian': [
                f'+{sum(int((1 + effect / 100) * 1) for effect in aura_counter)}% Physical Damage Reduction',
                'While there are at least five nearby Allies, you and nearby Allies have Onslaught',
            ],
            'Necromancer': [
                f'{sum(int((1 + effect / 100) * 2) for effect in aura_counter)}% increased Attack and Cast Speed',
            ],
            'Deadeye': [
                'You and Nearby Allies have Tailwind',
            ],
            'Gathering Winds': [
                'You and Nearby Allies have Tailwind',
            ],
            'Unwavering Faith': [
                f'+{sum(int((1 + effect / 100) * 1) for effect in aura_counter)}% Physical Damage Reduction',
                f'{sum(round((1 + effect / 100) * 0.2, 1) for effect in aura_counter)}% of Life Regenerated per second',
            ],
            'Radiant Crusade': [
                'Deal 10% more Damage',
                'While there are at least five nearby Allies, you and nearby Allies have Onslaught',
            ],
            'Radiant Faith': [
                f'{char_stats.mana // 10} additional Energy Shield',
            ],
            'Unwavering Crusade': [
                '20% increased Attack, Cast and Movement Speed',
                '30% increased Area of Effect',
                'Nearby Enemies are Unnerved',
                'Nearby Enemies are Intimidated',
            ],
            'Commander of Darkness': [
                f'{sum(int((1 + effect / 100) * 3) for effect in aura_counter)}% increased Attack and Cast Speed',
                '30% increased Damage',
                '+30% to Elemental Resistances',
            ],
            'Essence Glutton': [
                'For each nearby corpse, you and nearby Allies Regenerate 0.2% of Energy Shield per second, '
                    'up to 2.0% per second',
                'For each nearby corpse, you and nearby Allies Regenerate 5 Mana per second, up to 50 per second',
            ],
            'Plaguebringer':
                [
                    'With at least one nearby corpse, you and nearby Allies deal 10% more Damage',
                    'With at least one nearby corpse, nearby Enemies deal 10% reduced Damage',
                ],
            'Malediction':
                [
                    'Nearby Enemies have Malediction',
                ],
            'Void Beacon':
                [
                    'Nearby Enemies have -20% to Cold Resistance',
                    'Nearby Enemies have -20% to Chaos Resistance',
                ],
            'Conqueror':
                [
                    'Nearby Enemies deal 20% less Damage',  # "hits and ailments" is not recognized by PoB,
                ],
            'Worthy Foe':
                [
                    'Nearby Enemies take 20% increased Damage',
                    "Your Hits can't be evaded",
                ],
            'Master of Metal':
                [
                    '+1000 to Armour',
                    'You deal 6 to 12 added Physical Damage for each Impale on Enemy',
                ],
        }
        if node_name not in ascendancies:
            return []
        return [f'//{node_name}'] + ascendancies[node_name]

    @staticmethod
    def item_aura(item: dict, char_stats: stats.Stats, aura_counter: list) -> list[str]:
        aura_string = []
        for modlist in ['implicitMods', 'explicitMods', 'craftedMods', 'fracturedMods', 'enchantMods']:
            for mod in item.get(modlist, []):
                if m := re.search(r'Nearby Allies have (|\+)(\d+)% (.*) per 100 (.*) you have', mod, re.IGNORECASE):
                    # mask of the tribunal
                    value = int(m.group(2)) * getattr(char_stats, m.group(4).lower(), 0) // 100
                    aura_string.append(f'{m.group(1) if m.group(1) else ""}{value}% {m.group(3)}')
                elif m := re.search(r'Auras from your Skills grant (|\+)(\d+)(.*) to you and Allies', mod,
                                    re.IGNORECASE):
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
            aura_string = [f'// {item["name"]} {item["typeLine"]}', *aura_string]
        return aura_string


if __name__ == '__main__':
    character_stats, character, allocated_passives = stats.fetch_stats('raylu', 'auraraylu')
    skill_gems: list[gems.SkillGem] = []
    for i in character['items']:
        skill_gems.extend(gems.parse_skills_in_item(i, character_stats))
    aura_results = Auras().analyze_auras(character_stats, character, skill_gems, allocated_passives)
    print('\n\n'.join('\n'.join(ar) for result in aura_results for ar in result))
