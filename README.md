# PoE calculator (currently only for auras)

live version: https://poecalc.fly.dev

## setup

1.
```sh
mkdir data
cd data
wget https://raw.githubusercontent.com/ltogniolli/RePoE/master/RePoE/data/gems.json
wget https://raw.githubusercontent.com/ltogniolli/RePoE/master/RePoE/data/stat_translations/aura_skill.json
wget https://raw.githubusercontent.com/ltogniolli/RePoE/master/RePoE/data/stat_translations/curse_skill.json
wget https://github.com/Liberatorist/TimelessEmulator/blob/master/TimelessEmulator/Build/Output/TimelessJewels/TimelessJewels.zip
wget https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding/dev/src/Data/LegionPassives.lua
```
2. `pip3 install -r requirements.txt`
3. `./poecalc.py`
