"""PF2e-specific typed builders: authored source, never inferred Actor mechanics.

Syntax boundary: https://github.com/foundryvtt/pf2e/wiki/Style-Guide
Versioned vocabulary is documented in inline_models; only 14.369/8.6.1 admitted.
"""
import json
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import Tool, ToolResult
from mcp.types import TextContent, ToolAnnotations
from pydantic import ValidationError

from . import inline_models as M
from .selective import rpc


def arithmetic(amount):
    """Format bounded typed arithmetic; no caller formula string is accepted."""
    dice = '+'.join(f'{d.count}d{d.faces}' for d in amount.dice)
    return dice + (f'{amount.modifier:+}' if amount.modifier else '') if dice else str(amount.modifier)


def format_source(request):
    """PF2e-specific guide-ordered notation, source amounts only, no evaluation."""
    formulas = []
    label = getattr(request, 'label', None)
    if isinstance(request, M.RollRequest):
        roll = request.roll
        label = roll.label
        if isinstance(roll, M.NonDamage):
            formula = arithmetic(roll.amount)
            formulas.append(formula)
            command = {'public': 'r', 'gm': 'gmr', 'blind': 'br', 'self': 'sr'}[roll.visibility]
            text = f'[[/{command} {formula}' + (f' #{roll.flavor}' if roll.flavor else '') + ']]'
        else:
            instances = []
            for instance in roll.damage:
                base = arithmetic(instance.amount)
                formulas.append(base)
                for category in ('precision', 'splash'):
                    component = getattr(instance, category)
                    if component is not None:
                        term = arithmetic(component)
                        formulas.append(term)
                        base += f'+({term}[{category}])'
                # Parentheses bind every component to the outer damage type.
                instances.append(f'({base})[' + ('persistent,' if instance.persistent else '') + instance.type + ']')
            text = '@Damage[' + ','.join(instances)
            if roll.options:
                text += '|options:' + ','.join(roll.options)
            text += ']'
    elif isinstance(request, M.CheckRequest):
        parts = [request.statistic]
        for key in ('defense', 'against', 'dc'):
            value = getattr(request, key)
            if value is not None:
                parts.append(f'{key}:{value}')
        default_role = 'target' if request.statistic in ('fortitude', 'reflex', 'will') else 'origin'
        if request.roller_role and request.roller_role != default_role:
            parts.append('rollerRole:' + request.roller_role)
        if request.basic:
            parts.append('basic')
        if request.show_dc != 'owner':
            parts.append('showDC:' + request.show_dc)
        if request.adjustment:
            parts.append(f'adjustment:{request.adjustment}')
        if request.immutable:
            parts.append('immutable')
        if request.name:
            parts.append('name:' + request.name)
        for key in ('traits', 'options'):
            if getattr(request, key):
                parts.append(key + ':' + ','.join(getattr(request, key)))
        if request.override_traits:
            parts.append('overrideTraits')
        text = '@Check[' + '|'.join(parts) + ']'
    else:
        text = '@Embed[' + request.item_uuid + ' inline' + (' hr=false' if request.suppress_hr else '') + ']'
    if label:
        text += '{' + label + '}'
    if len(text.encode('utf-8')) > 8000:
        raise ToolError('SourceTooLarge: generated source exceeds 8000 UTF-8 bytes; reduce terms/options. Nothing was truncated.')
    return text, formulas


class InlineTool(Tool):
    """PF2e-specific input/output validation through the actual FastMCP boundary."""
    request_model: Any

    async def run(self, arguments):
        try:
            request = self.request_model.model_validate(arguments)
        except ValidationError as exc:
            issues = [{'field': '.'.join(map(str, e['loc'])), 'message': e['msg']} for e in exc.errors(include_input=False, include_url=False)]
            raise ToolError('InvalidRequest: ' + json.dumps(issues) + '; inspect this tool schema and correct the structured mechanics.') from None
        text, formulas = format_source(request)
        method = {M.RollRequest: 'verifyPF2eInlineRoll', M.CheckRequest: 'verifyPF2eInlineCheck', M.EmbedRequest: 'verifyPF2eInlineEmbed'}[type(request)]
        params = dict(text=text, formulas=formulas)
        if isinstance(request, M.EmbedRequest):
            params['item_uuid'] = request.item_uuid
        result = await rpc(method, params)
        try:
            validated = M.InlineResponse.model_validate(result)
            if validated.text != text:
                raise ValueError('source mismatch')
        except (ValidationError, ValueError, TypeError):
            raise ToolError('InvalidFoundryResponse: inline verification failed its typed source/runtime contract; update server/module together.') from None
        result = validated.model_dump(mode='json')
        return ToolResult(content=[TextContent(type='text', text=text)], structured_content=result)


def install(server):
    """Register three independent PF2e-specific typed tools, no selective reads."""
    common = (' Requires a connected ready GM on Foundry14.369/PF2e8.6.1; other systems/versions error. '
              'Returns exactly one text block of insertable source and structured {text,runtime:{core_version,system_id,system_version}}. '
              'No chat, document writes, dice evaluation or effects. No select/pagination; 8000 UTF-8 bytes maximum, reject rather than truncate. '
              'InvalidRequest: correct schema/combination/delimiters; BridgeUnavailable/NotReady: reconnect ready GM; '
              'PermissionDenied: use authorized GM/readable document; UnsupportedSystem/UnsupportedVersion: use verified runtime; '
              'InvalidFormula: correct dice mechanics; DocumentNotFound: rediscover UUID. '
              'Verification does not establish future targets, Actor modifiers or identical chat/journal/Item rendering. '
              'Use the returned text in a draft or future writer; generation itself inserts nothing. ')
    for name, model, description in (
        ('create_pf2e_inline_roll', M.RollRequest, 'PF2e-specific: build one deferred non-damage roll or typed damage link. Structured roll discriminates kind; no formula strings, dynamic references or advanced expressions. Damage excludes visibility/flavor. Example: {"roll":{"kind":"non_damage","amount":{"dice":[{"count":1,"faces":20}],"modifier":17},"flavor":"Counteract"}}.'),
        ('create_pf2e_inline_check', M.CheckRequest, 'PF2e-specific: build one check button from one statistic and at most one DC method. Saves, Perception, flat, full standard skills and Lore slugs only; custom statistics deferred. Named DCs need future origin/target context. Example: {"statistic":"reflex","dc":20,"basic":true}.'),
        ('create_pf2e_inline_embed', M.EmbedRequest, 'PF2e-specific: build an inline compendium Item embed after checking canonical UUID and pack/document read access; no body returned. Discover Item UUIDs using list_actor_compendiums then search_compendium_actors; read_item verifies identity. Missing is distinct from denied. Example: {"item_uuid":"Compendium.pf2e.feats-srd.Item.39CqlOzlHjEhh0E4","suppress_hr":true}.'),
    ):
        server.add_tool(InlineTool(name=name, description=description + common, parameters=model.model_json_schema(), output_schema=M.InlineResponse.model_json_schema(), request_model=model,
                                   annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)))
