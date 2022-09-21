import re
from copy import copy
from enum import Enum
from typing import Union
import data

all_gems, aura_text = data.load()


class GemQualityType(Enum):
    Superior = 0
    Anomalous = 1
    Divergent = 2
    Phantasmal = 3


class Skill:
    name: str
    level: int
    quality: int
    socketed: bool
    tags: set
    quality_type: GemQualityType

    def __init__(self, skill_dict: dict, socketed: bool) -> None:
        self.name = skill_dict['baseType']
        self.level = 1
        self.quality = 0
        self.socketed = socketed
        gem_data = self.get_gem_data()
        self.tags = {gem_tag.lower() for gem_tag in (gem_data.get('tags', []) + gem_data.get('types', []))}

        for prop in skill_dict['properties']:
            if prop['name'] == 'Level':
                self.level = int(re.search(r'(\d+)', prop['values'][0][0]).group(1))
            elif prop['name'] == 'Quality':
                self.quality = int(re.search(r'(\d+)', prop['values'][0][0]).group(1))

        self.quality_type = GemQualityType.Superior
        for quality_type in GemQualityType:
            if quality_type.name in skill_dict['typeLine']:
                self.quality_type = quality_type
                break

    def add_levels(self, level_mods: list[tuple[set[str], int]]) -> None:
        for required_tags, level in level_mods:
            if len(required_tags - self.tags) == 0:
                self.level += level

    def add_quality(self, quality_mods: list[tuple[set[str], int]]) -> None:
        for required_tags, quality in quality_mods:
            if len(required_tags - self.tags) == 0:
                self.quality += quality

    def iterate_effects(self, get_vaal_effect: bool = True) -> list[tuple[str, int]]:
        effects = []
        gem_data = self.get_gem_data(get_vaal_effect)
        for stat, value in zip(gem_data['static']['stats'], gem_data['per_level'][str(self.level)].get('stats', [])):
            if value is None:
                value = stat.get('value')
            else:
                value = value.get('value')
            effects.append((stat['id'], value))
        quality_effect = gem_data['static']['quality_stats'][self.quality_type.value]
        effects.append((quality_effect['id'], int(quality_effect['value'] * self.quality / 1000)))
        return effects

    def get_gem_data(self, get_vaal_effect: bool = True) -> dict:
        if self.name.startswith('Vaal') and not get_vaal_effect:
            return all_gems[self.name[5:]]
        return all_gems[self.name]


class SupportSkill(Skill):
    allowed_types: set
    excluded_types: set
    added_types: set
    support_gems_only: bool

    def __init__(self, gem_dict: dict, socketed: bool) -> None:
        super().__init__(gem_dict, socketed)
        self.allowed_types = {gem_type.lower() for gem_type in self.get_gem_data()['support_gem']['allowed_types']}
        self.excluded_types = {gem_type.lower() for gem_type in self.get_gem_data()['support_gem']['excluded_types']}
        self.support_gems_only = self.get_gem_data()['support_gem']['supports_gems_only']
        self.added_types = {gem_type.lower() for gem_type in self.get_gem_data()['support_gem'].get('added_types', [])}

    def can_support(self, active_skill_gem: Skill):
        if self.support_gems_only and not active_skill_gem.socketed:
            return False
        if self.allowed_types and len(self.allowed_types & active_skill_gem.tags) == 0:
            return False
        return len(active_skill_gem.tags & self.excluded_types) == 0


class ActiveSkill(Skill):
    aura_effect: int
    supports: list

    def __init__(self, gem_dict: dict, socketed: bool) -> None:
        super().__init__(gem_dict, socketed)
        self.aura_effect = 176
        self.supports = []
        self.tags |= {gem_type.lower() for gem_type in self.get_gem_data()['active_skill']['types']}
        self.tags.add(self.name.lower())

    def add_effect(self, effect: int) -> None:
        self.aura_effect += effect

    def applies_to_allies(self) -> bool:
        return 'aura' in self.tags and 'auraaffectsenemies' not in self.tags

    def apply_supports(self, support_gems: list[SupportSkill]):
        for support_gem in support_gems:
            if not support_gem.can_support(self):
                continue
            self.tags |= support_gem.added_types
            has_effect = False
            for stat, value in support_gem.iterate_effects():
                if stat in ['non_curse_aura_effect_+%', 'aura_effect_+%']:
                    self.aura_effect += value
                elif stat == 'supported_aura_skill_gem_level_+':
                    self.level += value
                elif stat == 'supported_active_skill_gem_quality_%':
                    self.quality += value
                else:
                    continue
                has_effect = True
            if has_effect:
                self.supports.append(support_gem)

    def get_aura(self, get_vaal_effect: bool) -> list[str]:
        aura_result = []
        previous_value = None
        for stat, value in self.iterate_effects(get_vaal_effect):
            if stat not in aura_text:
                continue
            value = scaled_value(value, self.aura_effect, aura_text[stat]['index_handlers'][0])
            if len(aura_text[stat]['format']) > 1:
                if previous_value is not None:
                    formatted_text = aura_text[stat]['string'].format(previous_value, value)
                    previous_value = None
                else:
                    previous_value = value
                    continue
            else:
                formatted_text = aura_text[stat]['string'].format(value)

            if m := re.search('you and nearby allies( deal| have| gain| are|) (.*)', formatted_text, re.IGNORECASE):
                aura_result.append(m.group(2))
            elif m := re.search("nearby allies' (.*)", formatted_text, re.IGNORECASE):
                aura_result.append(f'Your {m.group(1)}')
            elif formatted_text.startswith('Aura grants ') or formatted_text.startswith('Buff grants '):
                aura_result.append(formatted_text[len('Aura grants '):])
            elif not formatted_text.startswith('You and nearby Non-Minion Allies have a '):
                raise Exception(f'unhandled formatted line from {self.name}: {formatted_text}')

        if not aura_result:
            return []

        if self.supports:
            support_comment = '(' + ', '.join(f'{sup.name} {sup.level}' for sup in self.supports) + ')'
        else:
            support_comment = ''
        name = self.name
        if name.startswith('Vaal') and not get_vaal_effect:
            name = name[5:]
        special_quality = f'{self.quality_type.name} ' if self.quality_type != GemQualityType.Superior else ''
        header = f'// {special_quality}{name} (lvl {self.level}, {self.quality}%) {support_comment} {self.aura_effect}%'
        return [header] + aura_result


def item_gem_dict(mod_string: str) -> dict:
    if m := re.match(r'Socketed Gems are Supported by Level (\d+) (.+)', mod_string):
        name = m.group(2) + ' Support'
        support = True
    elif m := re.match(r'Grants Level (\d+) (.+) Skill', mod_string):
        name = m.group(2)
        support = False
    else:
        raise ValueError(f'Could not parse skill from mod: {mod_string}')
    level = m.group(1)
    return {'support': support, 'typeLine': name, 'baseType': name,
            'properties': [{'name': 'Level', 'values': [[str(level)]]}, {'name': 'Quality', 'values': [['+0%']]}]}


def scaled_value(value: int, aura_effect: int, index_handlers: list[str]) -> Union[int, float]:
    allow_float = False
    for handler in index_handlers:
        if handler == 'per_minute_to_per_second':
            value /= 60
            allow_float = True
        else:
            raise Exception('unhandled index_handler: ' + handler)
    value *= 1 + aura_effect / 100
    if allow_float:
        value = round(value, 1)
    else:
        value = int(value)
    return value


def parse_skills_in_item(item: dict, char_stats) -> list[ActiveSkill]:
    socketed_items = item.get('socketedItems', [])
    active_skills = [ActiveSkill(skill, socketed=True) for skill in socketed_items if skill.get('support') is False]
    support_skills = [SupportSkill(skill, socketed=True) for skill in socketed_items if skill.get('support')]
    level_mods = copy(char_stats.global_gem_level_increase)
    quality_mods = copy(char_stats.global_gem_quality_increase)
    for mod_type in ['explicitMods', 'implicitMods']:
        for mod in item.get(mod_type, []):
            if m := re.search(r'(.\d+) to Level of Socketed (.*)Gems', mod):
                level_mods += parse_gem_descriptor(m.group(2), int(m.group(1)))
            elif m := re.search(r'(.\d+)% to Quality of Socketed (.*)Gems', mod):
                quality_mods += parse_gem_descriptor(m.group(2), int(m.group(1)))
            elif 'Grants Level' in mod:
                active_skills.append(ActiveSkill(item_gem_dict(mod), socketed=False))
            elif 'Socketed Gems are Supported by Level' in mod:
                support_skills.append(SupportSkill(item_gem_dict(mod), socketed=False))

    for skill in support_skills + active_skills:
        if skill.socketed:
            skill.add_levels(level_mods)
            skill.add_quality(quality_mods)
    for skill in active_skills:
        skill.apply_supports(support_skills)
    return active_skills


def parse_gem_descriptor(descriptor: Union[None, str], value: int) -> list[tuple[set, int]]:
    if descriptor is None:
        # since active skills and supports are mutually exclusive, we can increase both if no conditions are specified
        return [({'active_skill'}, value), ({'support'}, value)]
    descriptor = descriptor[:-1].lower()

    if 'non-' in descriptor:  # handles vaal caress - decreases all gem levels and then sets all vaal gems back to 0
        return [({'active_skill'}, value), ({'support'}, value), ({descriptor[4:]}, -value)]

    required_tags = set()
    if 'skill' in descriptor:
        required_tags.add('active_skill')
    if 'aoe' in descriptor:
        required_tags.add('area')

    all_tags = frozenset([
        'mark', 'strength', 'duration', 'link', 'critical', 'chaos', 'nova', 'spell', 'trigger', 'bow', 'attack',
        'slam', 'warcry', 'guard', 'channelling', 'travel', 'strike', 'blessing', 'low_max_level', 'intelligence',
        'cold', 'totem', 'projectile', 'orb', 'stance', 'brand', 'dexterity', 'physical', 'lightning', 'fire', 'aura',
        'melee', 'chaining', 'herald', 'mine', 'exceptional', 'minion', 'curse', 'hex', 'movement', 'vaal', 'support',
        'banner', 'golem', 'trap', 'blink', 'random_element', 'arcane'
    ])
    required_tags |= (all_tags & set(descriptor.split()))
    return [(required_tags, value)]
