"""PF2e-specific inline source contracts, Foundry14.369/PF2e8.6.1.

Authored mechanics only, never Actor-derived values. Vocabulary:
https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/damage/values.ts
Syntax: https://github.com/foundryvtt/pf2e/wiki/Style-Guide
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


Number = Annotated[int, Field(ge=-10000, le=10000)]
Text = Annotated[str, Field(min_length=1, max_length=200, pattern=r'^[^\[\]{}|#@<>\\&\x00-\x1f\x7f]+$', description='Plain text; inline/HTML delimiters, ampersands, backslashes and control characters are rejected, not escaped.')]
Option = Annotated[str, Field(min_length=1, max_length=200, pattern=r'^[a-z0-9]+(?:[-:][a-z0-9]+)*$', description='Literal lowercase trait or roll-option slug; colon-separated namespaces allowed, no formulas or delimiters.')]
Options = Annotated[list[Option], Field(max_length=32)]
Statistic = Literal['flat', 'perception', 'fortitude', 'reflex', 'will', 'acrobatics', 'arcana', 'athletics', 'crafting', 'deception', 'diplomacy', 'intimidation', 'medicine', 'nature', 'occultism', 'performance', 'religion', 'society', 'stealth', 'survival', 'thievery']
Lore = Annotated[str, Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*-lore$', max_length=200, description='Owned Lore slug, e.g. engineering-lore; existence is not verified.')]
DCStatistic = Literal['ac', 'perception', 'fortitude', 'reflex', 'will', 'acrobatics', 'arcana', 'athletics', 'crafting', 'deception', 'diplomacy', 'intimidation', 'medicine', 'nature', 'occultism', 'performance', 'religion', 'society', 'stealth', 'survival', 'thievery', 'class', 'spell', 'class-spell']
DamageType = Literal['acid', 'bleed', 'bludgeoning', 'cold', 'electricity', 'fire', 'force', 'mental', 'piercing', 'poison', 'slashing', 'sonic', 'spirit', 'untyped', 'vitality', 'void']


class Die(Model):
    count: int = Field(ge=1, le=100, description='Number of additive dice, 1–100.')
    faces: Literal[4, 6, 8, 10, 12, 20, 100] = Field(description='Standard die faces; damage amounts allow only d4/d6/d8/d10/d12.')

    @field_validator('faces', mode='before')
    @classmethod
    def integer_faces(cls, value):
        """Literal enums must also reject float/bool primitive coercion."""
        if type(value) is not int:
            raise ValueError('faces must be an integer, not a string, float or boolean.')
        return value


class Amount(Model):
    dice: list[Die] = Field(default_factory=list, max_length=16, description='Up to 16 additive dice terms; empty means a numeric constant.')
    modifier: Number = Field(default=0, description='Signed integer added after dice; alone is a constant, including zero.')


class NonDamage(Model):
    kind: Literal['non_damage'] = Field(description='Build a deferred core roll link, never an evaluated roll.')
    amount: Amount = Field(description='Structured arithmetic; arbitrary formulas and data references are unsupported.')
    visibility: Literal['public', 'gm', 'blind', 'self'] = Field(default='public', description='Audience of the eventual roll, independent of the containing message audience.')
    flavor: Text | None = Field(default=None, description='Optional eventual roll flavor, up to 200 characters.')
    label: Text | None = Field(default=None, description='Optional button label, up to 200 characters.')


class DamageInstance(Model):
    type: DamageType = Field(description='PF2e8.6.1 damage type, including explicit untyped.')
    amount: Amount = Field(description='Base damage arithmetic; d4 through d12 only.')
    persistent: bool = Field(default=False, description='Mark this whole instance persistent; incompatible with precision/splash components.')
    precision: Amount | None = Field(default=None, description='Optional precision component of the same type; not a separate instance.')
    splash: Amount | None = Field(default=None, description='Optional splash component of the same type; not a separate instance.')

    @model_validator(mode='after')
    def categories(self):
        """PF2e-specific mutually exclusive categories and standard damage dice."""
        if self.persistent and (self.precision is not None or self.splash is not None):
            raise ValueError('Persistent damage cannot include precision or splash; use separate instances.')
        for amount in (self.amount, self.precision, self.splash):
            if amount and any(d.faces not in (4, 6, 8, 10, 12) for d in amount.dice):
                raise ValueError('Damage dice require faces 4, 6, 8, 10 or 12.')
        return self


class Damage(Model):
    kind: Literal['damage'] = Field(description='Build PF2e @Damage source; visibility and flavor are unsupported.')
    damage: list[DamageInstance] = Field(min_length=1, max_length=16, description='1–16 independent typed damage instances, in order.')
    options: Options = Field(default_factory=list, description='Additional literal roll options; no trait/Actor inference.')
    label: Text | None = Field(default=None, description='Optional button label, up to 200 characters.')


class RollRequest(Model):
    roll: Annotated[NonDamage | Damage, Field(discriminator='kind')] = Field(description='Choose exactly one structured non_damage or damage variant.', examples=[{'kind': 'damage', 'damage': [{'type': 'fire', 'amount': {'dice': [{'count': 2, 'faces': 6}], 'modifier': 3}}], 'label': 'Flaming burst'}])


class CheckRequest(Model):
    statistic: Statistic | Lore = Field(description='One save, flat, Perception, standard full skill slug or Lore slug. Custom statistics excluded.', examples=['reflex', 'engineering-lore'])
    dc: Annotated[int, Field(ge=1, le=10000)] | None = Field(default=None, description='Fixed DC; mutually exclusive with against and defense. No expressions.')
    against: DCStatistic | None = Field(default=None, description='Named DC statistic; opposed side depends on roller_role. Requires future origin/target context.')
    defense: DCStatistic | None = Field(default=None, description='Named target defense; mutually exclusive with dc and against.')
    roller_role: Literal['origin', 'target'] | None = Field(default=None, description='Requires against. Default is target for saves, origin otherwise; matching defaults are omitted.')
    basic: bool = Field(default=False, description='Basic damage save; requires fortitude, reflex or will.')
    show_dc: Literal['owner', 'gm', 'all', 'none'] = Field(default='owner', description='Who sees the eventual DC; owner default is omitted.')
    adjustment: Number = Field(default=0, description='Signed DC adjustment; zero is omitted.')
    immutable: bool = Field(default=False, description='Keep the eventual DC static; omit default false.')
    name: Text | None = Field(default=None, description='Optional check name in eventual chat card, up to 200 characters.')
    traits: Options = Field(default_factory=list, description='Additional traits; secret requests an eventual blind roll. Does not verify trait automation.')
    options: Options = Field(default_factory=list, description='Additional roll options such as damaging-effect.')
    override_traits: bool = Field(default=False, description='Omit inherited Item traits from the eventual check.')
    label: Text | None = Field(default=None, description='Optional button label; recommended for Lore.')

    @model_validator(mode='after')
    def combinations(self):
        """PF2e-specific check constraints from the upstream Style Guide."""
        if sum(v is not None for v in (self.dc, self.against, self.defense)) > 1:
            raise ValueError('Use only one of dc, against or defense.')
        if self.basic and self.statistic not in ('fortitude', 'reflex', 'will'):
            raise ValueError('basic requires a save statistic.')
        if self.roller_role is not None and self.against is None:
            raise ValueError('roller_role requires against.')
        return self


class EmbedRequest(Model):
    item_uuid: str = Field(pattern=r'^Compendium\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.Item\.[A-Za-z0-9]{16}$', max_length=512, description='Canonical compendium Item UUID from search_compendium_actors (Item packs) or read_item; never a name, local ID, world Item or embedded Item.', examples=['Compendium.pf2e.feats-srd.Item.39CqlOzlHjEhh0E4'])
    suppress_hr: bool = Field(default=False, description='Emit hr=false to suppress horizontal rules; inline is always emitted.')


class Runtime(Model):
    core_version: Literal['14.369'] = Field(description='Foundry version verified on this invocation.')
    system_id: Literal['pf2e'] = Field(description='Verified PF2e system ID.')
    system_version: Literal['8.6.1'] = Field(description='PF2e version verified on this invocation.')


class InlineResponse(Model):
    text: str = Field(min_length=1, max_length=8000, description='Insertable source, bounded to 8000 UTF-8 bytes; never rendered HTML.')
    runtime: Runtime = Field(description='Connected ready GM runtime used for non-evaluating verification.')
