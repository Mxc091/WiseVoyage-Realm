"""Station context, bounded walking plans and grounded public consultation."""
import math
import re
import json
from pathlib import Path
from datetime import datetime
from .walking_network import NETWORK, access_point, anchor_distance, anchor_to_anchor_distance, distance_between, network_version
from .route_presentation import route_overview
from .tour_language import ENGLISH_PLACE_NAMES
from .route_order import optimize_order
from .route_recommender import _features

ENGLISH = json.loads((Path(__file__).resolve().parents[3]/'data/station_public_english.json').read_text(encoding='utf-8'))


def english_local_answer(spot, answer):
    translated = ENGLISH.get(answer)
    if translated: return translated
    # Prefer a published English description to an invented translation when the
    # provider is unavailable. Specific missing details remain explicitly unknown.
    description = ENGLISH.get(spot.get('description', ''))
    return (description + '\n\nFor further details, try the digital guide again or ask on-site staff.' if description else
            'A verified English explanation for this question is temporarily unavailable. You can browse the attraction information or ask on-site staff.')


def anchors():
    return {**{'gate:' + k: v for k, v in NETWORK['gates'].items()},
            **{'spot:' + k: v for k, v in NETWORK['anchors'].items()}}


def station_anchor(station):
    source = anchors().get(station.anchor_key)
    if not source:
        raise ValueError('本站步行起点尚未配置，请联系工作人员')
    return dict(source, label=station.name, label_en=station.name_en)


def _step_alternative(base, selected, options, budget):
    """Minimize mapped stair distance over per-leg alternatives within the full trip budget."""
    if options['avoid_steps']:
        return []
    route = base['route']
    def ordered_legs(plan):
        return [plan['entry_leg'], *plan['legs'], plan['exit_leg']]
    original = ordered_legs(route)
    original_steps = sum(leg['steps_meters'] for leg in original)
    if not original_steps:
        return []
    detours = ordered_legs(route_overview(selected, **{**options, 'avoid_steps': True}))
    visit = route['visit_minutes']
    factor = .15 if options['pace'] == 'relaxed' else .08
    # For each walking time keep the combination with the fewest stair meters.
    states = {0: (0, 0, ())}
    for direct, detour in zip(original, detours):
        variants = [direct]
        if detour['available'] and detour['steps_meters'] < direct['steps_meters']:
            variants.append(detour)
        layer = {}
        for elapsed, (stairs, distance, picks) in states.items():
            for index, leg in enumerate(variants):
                minutes = elapsed + leg['minutes']
                active = visit + minutes
                if active + math.ceil(active * factor) > budget:
                    continue
                value = (stairs + leg['steps_meters'], distance + leg['meters'], picks + (index,))
                if minutes not in layer or value < layer[minutes]:
                    layer[minutes] = value
        states = layer
    if not states:
        return []
    stairs, minutes, distance, picks = min((v[0], t, v[1], v[2]) for t, v in states.items())
    if stairs >= original_steps:
        return []
    legs = [detours[i] if detour else original[i] for i, detour in enumerate(picks)]
    rest = math.ceil((visit + minutes) * factor)
    variant = dict(route, entry_leg=legs[0], legs=legs[1:-1], exit_leg=legs[-1],
                   walking_meters=distance, walking_minutes=minutes-legs[-1]['minutes'],
                   exit_minutes=legs[-1]['minutes'], rest_minutes=rest, total_minutes=visit+minutes+rest)
    return [dict(kind='stairs', title='少台阶走法', title_en='Fewer mapped stairs', route=variant,
                 stairs_saved=original_steps-stairs, extra_minutes=variant['total_minutes']-route['total_minutes'])]


class StationRouteConflict(ValueError):
    """The requested journey conflicts with walking connectivity or its time budget."""


class StationBudgetConflict(StationRouteConflict):
    def __init__(self, route, budget, english):
        self.route = route
        minutes = route['total_minutes']
        super().__init__(f'The selected stops need {minutes} minutes, {minutes-budget} more than the {budget}-minute budget.'
                         if english else f'按当前步速，游览全部已选景点并到达终点预计需要 {minutes} 分钟，比 {budget} 分钟预算多 {minutes-budget} 分钟。')


def _check_walk_connections(start, end, selected, avoid_steps, english, allow_relaxation=True):
    """On this undirected graph, all required stops and the exit must be reachable from the start."""
    def label(anchor):
        name = anchor['label']
        return (anchor.get('label_en') or ENGLISH_PLACE_NAMES.get(name, name)) if english else name

    points = [(ENGLISH_PLACE_NAMES.get(s['spot_name'], s['spot_name']) if english else s['spot_name'],
               access_point(s)) for s in selected]
    targets = [*points, ((f'Exit: {label(end)}' if english else f'终点{label(end)}'), end)]
    blocked = [(name, point) for name, point in targets
               if not math.isfinite(anchor_to_anchor_distance(start, point, avoid_steps))]
    if not blocked:
        return
    separator = ', ' if english else '、'
    stairs, disconnected = [], []
    for name, point in blocked:
        if avoid_steps and math.isfinite(anchor_to_anchor_distance(start, point)):
            stairs.append(name)
        else:
            disconnected.append(name)
    lines = []
    if stairs:
        names = separator.join(stairs)
        lines.append(f'From {label(start)}, all mapped paths to {names} require marked steps.'
                     if english else f'从{label(start)}出发，当前路网中通往{names}的步行路径都要经过已标注台阶。')
    if disconnected:
        names = separator.join(disconnected)
        lines.append(f'No walking path is mapped from {label(start)} to {names}, even with steps allowed.'
                     if english else f'从{label(start)}到{names}，即使允许走台阶，当前路网也找不到连通的步行路径。')
    blocked_names = {name for name, _ in blocked}
    reachable = separator.join(name for name, _ in points if name not in blocked_names)
    if reachable:
        lines.append(f'Reachable from the start: {reachable}.' if english else f'从起点可以到达的已选景点有{reachable}。')
    if blocked[-1] == targets[-1]:
        near_exit = separator.join(name for name, point in points if name in blocked_names
                                   and math.isfinite(anchor_to_anchor_distance(point, end, avoid_steps)))
        if near_exit:
            lines.append(f'{near_exit} connects to {label(end)}, but this section is disconnected from the start.'
                         if english else f'{near_exit}与{label(end)}之间可以步行，但起点无法接入这一段。')
    if stairs and not disconnected and allow_relaxation:
        lines.append('If stairs are suitable, turn off “Avoid marked steps” to keep all stops and the exit.'
                     if english else '如果可以走台阶，取消“避开路网已标注的台阶”即可保留全部选点和终点，再按原预算重算。')
    lines.append('To keep the walking restrictions, change the unreachable destinations. More time or a different order cannot connect these sections.'
                 if english else '若保留当前通行条件，请调整上面列出的不可达目的地。增加游览时间或调换顺序都无法连通这些路段。')
    raise StationRouteConflict('\n'.join(lines))


def plan_walk(station, spots, preferences):
    """Bounded insertion search with diminishing returns for each interest theme."""
    budget = preferences['budget']
    start_time, exit_by = preferences.get('start_time'), preferences.get('exit_by')
    if start_time or exit_by:
        if not (start_time and exit_by and exit_by > start_time):
            raise ValueError('请填写同一天的出发与最晚离园时间，离园时间应晚于出发时间')
        def minutes(clock):
            hour, minute = map(int, clock.split(':'))
            return hour * 60 + minute
        budget = min(budget, minutes(exit_by) - minutes(start_time))
    start = station_anchor(station)
    end = start if preferences['end_area'] == 'return' else NETWORK['gates'][preferences['end_area']]
    options = dict(pace=preferences['pace'], start_anchor=start, end_anchor=end,
                   avoid_steps=preferences['avoid_steps'])
    allowed = [s for s in spots if access_point(s)]
    requested = preferences.get('spot_ids', [])
    skipped = set(preferences.get('skip_ids', []))
    dwell = preferences.get('dwell_minutes', {})
    if skipped.intersection(requested):
        raise ValueError('同一景点不能同时设为必去和跳过')
    allowed = [dict(s, visit_duration=dwell.get(s['spot_id'], s.get('visit_duration')))
               for s in allowed if s['spot_id'] not in skipped]
    profile = preferences.get('personalization') or {}
    priority = {int(key): 1 / (1 + index * .2) for index, key in enumerate(profile.get('matches', {}))}
    related = set(priority) - set(requested) if profile.get('related_stops') else set()
    if requested and related and not preferences.get('fill_time'):
        allowed = [s for s in allowed if s['spot_id'] in requested or s['spot_id'] in related]
    seed = []
    if requested:
        lookup = {s['spot_id']: s for s in allowed}
        if len(set(requested)) != len(requested) or any(s not in lookup for s in requested):
            raise ValueError('所选景点不可用或尚未接入本站步行路网')
        selected = [lookup[s] for s in requested]
    else:
        selected = []
    _check_walk_connections(start, end, selected, options['avoid_steps'], preferences.get('language') == 'en',
                            preferences.get('compare_with_steps', True))
    if selected:
        route = (optimize_order(selected, fixed_start=False, **options)['proposed_route']
                 if len(selected) > 1 else route_overview(selected, **options))
        if not route['complete']: raise ValueError('没有找到完整的步行路线，请调整景点或少台阶选项')
        if route['total_minutes'] > budget:
            raise StationBudgetConflict(route, budget, preferences.get('language') == 'en')
        if not preferences.get('fill_time') and not related:
            base = dict(kind='custom', title='自选景点顺路方案', title_en='Your selected stops', route=route)
            ordered = [lookup[s['spot_id']] for s in route['stops']]
            return [base, *_step_alternative(base, ordered, options, budget)]

        indices = {s['spot_id']: i for i, s in enumerate(allowed)}
        seed = [indices[s['spot_id']] for s in route['stops']]

    speed = 55 if preferences['pace'] == 'relaxed' else 75
    avoid = preferences['avoid_steps']
    edges = [[distance_between(a, b, avoid) for b in allowed] for a in allowed]
    entry = [anchor_distance(s, start, avoid) for s in allowed]
    exits = [anchor_distance(s, end, avoid) for s in allowed]
    visits = [max(1, int(s.get('visit_duration') or 10)) for s in allowed]
    themes = ('history', 'nature', 'photography', 'family')
    weights = preferences.get('interest_weights') or {}
    if not sum(weights.values()):
        legacy = preferences.get('interest', 'all')
        weights = {t: int(legacy == 'all' or t == ('photography' if legacy == 'photo' else legacy)) for t in themes}
    weight_sum = sum(weights.values()) or 1
    profiles = [_features(s)['affinities'] for s in allowed]
    rest_factor = .15 if speed == 55 else .08

    def benefit(stops):
        # Concavity reduces the marginal gain of repeatedly covering one theme.
        return sum(weights.get(t, 0) * math.sqrt(sum(profiles[i].get(t, 0) for i in stops))
                   for t in themes) / weight_sum + 4 * math.sqrt(sum(priority.get(allowed[i]['spot_id'], 0) for i in stops))

    def evaluate(path):
        legs = [entry[path[0]], *(edges[a][b] for a, b in zip(path, path[1:])), exits[path[-1]]]
        if not all(map(math.isfinite, legs)):
            return None
        active = sum(math.ceil(d / speed) for d in legs) + sum(visits[i] for i in path)
        minutes = active + math.ceil(active * rest_factor)
        if minutes <= budget:
            return (minutes, sum(legs), path)
        return None

    # Insert at any position, including before or between mandatory stops.
    # Keep the fastest feasible order seen for each distinct membership.
    pool = {}
    beam = [tuple(seed)]
    if seed:
        pool[frozenset(seed)] = evaluate(tuple(seed))
    for _ in range(max(0, min(len(allowed), max(8, len(seed))) - len(seed))):
        layer = {}
        for path in beam:
            for i in range(len(allowed)):
                if i in path:
                    continue
                key = frozenset((*path, i))
                for pos in range(len(path) + 1):
                    candidate = evaluate(path[:pos] + (i,) + path[pos:])
                    if candidate and (key not in layer or candidate < layer[key]):
                        layer[key] = candidate
        if not layer:
            break
        pool.update(layer)
        beam = [v[2] for k, v in sorted(layer.items(), key=lambda kv: (
            -benefit(kv[0]), kv[1]))[:72]]

    options_found = [(benefit(k), v) for k, v in pool.items() if v]
    if not options_found:
        raise StationRouteConflict('当前时间不足以完成本站出发并到达终点的游览，请增加时间或更换终点')
    best = min(options_found, key=lambda x: (-x[0], x[1]))
    if profile.get('less_walking'):
        best = min((v for v in options_found if v[0] >= .8 * best[0]),
                   key=lambda v: (v[1][1], -v[0], v[1][0]))
    choices = [('personal', '按您的需求推荐', 'Your personalized route', best)] if profile else [
        ('balanced', '兴趣优先', 'Interest match', best)]
    # Compare distance only among plans retaining at least 85% of the best found benefit.
    shorter = min((v for v in options_found if v[0] >= .85 * best[0] and v[1][0] <= best[1][0]),
                  key=lambda x: (x[1][1], -x[0], x[1][0]))
    if shorter[1][1] < best[1][1]:
        choices.append(('easy', '少走一些', 'Less walking', shorter))
    rich = min(options_found, key=lambda x: (-len(x[1][2]), -x[0], x[1]))
    if len(rich[1][2]) > max(len(v[3][1][2]) for v in choices):
        choices.append(('rich', '多看一些', 'More stops', rich))
    output = []
    for kind, title, title_en, (_, (_, _, path)) in choices:
        final = route_overview([allowed[i] for i in path], **options)
        if final['complete'] and final['total_minutes'] <= budget:
            output.append(dict(kind=kind, title=title, title_en=title_en, route=final))
    if not output:
        raise ValueError('路网已变化，请重新规划')
    selected_lookup = {s['spot_id']: s for s in allowed}
    ordered = [selected_lookup[s['spot_id']] for s in output[0]['route']['stops']]
    return output + _step_alternative(output[0], ordered, options, budget)


def extract_request(question, existing=None):
    """Conservative bilingual hints. A visible editable form always confirms them."""
    values = dict(existing or {})
    q = re.sub(r'(?<=\w)[-–](?=hours?\b)', ' ', question.lower())
    match = re.search(r'(\d{1,3})\s*(?:分钟|minutes?|mins?)', q)
    hours = re.search(r'(\d+(?:\.\d+)?)\s*(?:个?小时|hours?|hrs?)', q)
    if match: values['budget'] = max(20, min(480, int(match[1])))
    elif hours: values['budget'] = max(20, min(480, round(float(hours[1]) * 60)))
    else:
        chinese = re.search(r'([一二两三四五六七八])个?(半)?小时', q)
        english = re.search(r'\b(one|two|three|four|five|six|seven|eight)(?:\s+and\s+a\s+(half))?\s+hours?\b', q)
        if chinese:
            count={'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8}[chinese[1]]
            values['budget']=min(480,count*60+(30 if chinese[2] else 0))
        elif english:
            count=['one','two','three','four','five','six','seven','eight'].index(english[1])+1
            values['budget']=min(480,count*60+(30 if english[2] else 0))
        elif '半小时' in q or 'half an hour' in q: values['budget'] = 30
        elif '半天' in q: values['budget'] = 240
    if any(s in q for s in ('不要台阶', '少台阶', '轮椅', 'avoid stairs', 'wheelchair')): values['avoid_steps'] = True
    for words, area in [(('东门', '东宫门', 'east gate', 'east palace gate'), 'east'), (('北门', '北宫门', 'north gate', 'north palace gate'), 'north'), (('南门', '新建宫门', 'south gate', 'new palace gate'), 'south'), (('回到这里', '返回本站', '回到本站', '回本站', 'return here', 'return to this station'), 'return')]:
        if any(w in q for w in words): values['end_area'] = area; break
    return values


def consultation(question, station, spots, language):
    from .tour_language import query_aliases
    from .tour_dialogue import resolve_turn, local_answer
    from .tour_visuals import build_visual_context
    en = language == 'en'
    q = query_aliases(question)
    spot = next((s for s in sorted(spots, key=lambda s: -len(s['spot_name'])) if s['spot_name'] in q), None)
    wayfinding = bool(spot and re.search(r'怎么走|怎么到|如何到|how\s+(?:do|can)\s+i\s+(?:get|reach)|directions|way to', q, re.I))
    route_intent = any(s in q.lower() for s in ('规划', '路线', '怎么玩', '安排', 'plan', 'route', 'itinerary')) or (
        not spot and any(s in q.lower() for s in ('小时', '分钟', 'hour', 'minutes')))
    facility_intent = any(s in q.lower() for s in ('厕所', '卫生间', '饮水', '服务台', '出口', 'restroom', 'toilet', 'water', 'exit', 'facility'))
    if wayfinding: route_intent = False
    actions = ['plan'] if route_intent else ['facilities'] if facility_intent or wayfinding else ['explore']
    visuals = None
    if wayfinding:
        from .tour_language import ENGLISH_SPOT_NAMES
        answer = ('I can show the walking path from this station to ' + ENGLISH_SPOT_NAMES.get(spot['spot_name'], 'the attraction') + '. Use the directions button below to see the route and estimated walking time.' if en else
                  '我可以为您查看从本站到' + spot['spot_name'] + '的步行路线。点击下方入口，可在地图上查看路径与预计步行时间。')
    elif route_intent:
        answer = ('Check your time and end point in the planning form. You can also select the attractions you want to visit. The route starts at this station and includes walking, visits and breaks in the time estimate.' if en else
                  '请在规划表里确认游览时间和终点，也可以直接选择想去的景点。路线从本站出发，预计用时包含步行、景点停留和休息。')
    elif facility_intent:
        answer = ('Choose a published facility or exit below to see the walking path from this station. Unverified facilities and live opening conditions cannot be assumed; please ask staff if a service is not listed.' if en else
                  '您可以在设施与出口中查看已发布的位置，并计算从本站出发的步行路线。未核实的卫生间、饮水点不会推测标注；未列出的服务请咨询现场工作人员。')
    elif spot:
        turn = resolve_turn(q, spot)
        answer, _ = local_answer(turn, spot)
        visuals = build_visual_context(spot, turn.intents, answer, language)
        actions = ['explore', 'plan']
    else:
        answer = ('I am the digital receptionist at this fixed service station. Ask about a Summer Palace attraction, plan a walk, or find a published facility or exit. For example: “Please plan a two-hour visit.”' if en else
                  '我是固定在本站的数字接待员，可以介绍颐和园景点、从这里规划游览，也能帮您查找已发布的设施与出口。您可以说：“帮我安排两小时游览。”')
    return dict(answer=answer, actions=actions, visuals=visuals, spot=spot, route_intent=route_intent,
                destination_key='spot:'+spot['spot_name'] if wayfinding else None)


def revise_plan_request(question, snapshot, spots):
    """Only explicit route edits change the saved route; ordinary questions stay read-only."""
    from .tour_language import query_aliases
    q = query_aliases(question).lower()
    original = snapshot['preferences']
    values = extract_request(q, original)
    if not re.search(r'最后|离园|改为|换.*出口|返回本站|回到这里|finish|end at|return here', q):
        values['end_area'] = original['end_area']
    if not re.search(r'我有|只有|安排|改为|控制在|预算|within|have|budget|make|set|change', q):
        values['budget'] = original['budget']
    ids = [s['spot_id'] for s in snapshot['route']['stops']]
    changed = any(values.get(k) != original.get(k) for k in ('budget', 'end_area', 'avoid_steps'))
    shorter = bool(re.search(r'太远|太长|短一点|少走|shorter|too (?:long|far)', q))
    if shorter:
        values['budget'] = max(20, min(original['budget'] - 15, snapshot['route']['total_minutes'] - 10))
        if values['budget'] >= snapshot['route']['total_minutes']:
            raise ValueError('这条路线已很短，可以直接移除不想去的景点')
        changed = True
    edited_stops = False
    # Each clause is handled independently so “remove A, add B” stays unambiguous.
    for clause in re.split(r'[，,。;；]|然后|再去|\band\b', q):
        matched = [s['spot_id'] for s in spots if s['spot_name'].lower() in clause]
        remove = bool(re.search(r"去掉|删掉|移除|不去|不要去|不想去|不想看|不看|remove|skip|drop|don't want to visit|do not want to visit", clause))
        add = bool(re.search(r'加上|加入|增加|还想去|也想去|想去|add|include|want to visit', clause))
        if matched and (remove or add):
            edited_stops = changed = True
            ids = [i for i in ids if i not in matched] if remove else list(dict.fromkeys(ids + matched))
    if not changed:
        return None
    if edited_stops:
        values['skip_ids'] = [i for i in values.get('skip_ids', []) if i not in ids]
        values['fill_time'] = False
    if edited_stops and not ids:
        raise ValueError('路线至少保留一个景点，请先加入其他景点')
    # A shorter automatic itinerary may choose fewer stops. Explicit selections stay pinned.
    values['spot_ids'] = ids if edited_stops or not shorter else list(original.get('spot_ids', []))
    return values
