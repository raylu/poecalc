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
wget https://raw.githubusercontent.com/ltogniolli/RePoE/master/RePoE/data/stat_translations/passive_skill.json
wget https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding/dev/src/Data/LegionPassives.lua
wget https://raw.githubusercontent.com/Liberatorist/TimelessEmulator/master/TimelessEmulator/Build/Output/TimelessJewels/TimelessJewels.zip
unzip TimelessJewels.zip -d TimelessJewels
```
2. `pip3 install -r requirements.txt`
3. `./poecalc.py`
