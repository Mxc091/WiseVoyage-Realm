"""Feasible choices for the public terminal. Previews never write a station plan."""
import math
from itertools import combinations

from .station_service import plan_walk, station_anchor, StationRouteConflict, StationBudgetConflict
from .route_presentation import route_overview
from .walking_network import NETWORK, access_point, anchor_distance, anchor_to_anchor_distance


def _ids(plan):
    return {s['spot_id'] for s in plan['route']['stops']}


def _coverage(ids, party):
    first = sum(m['first'] in ids for m in party)
    represented = sum(m['first'] in ids or m['backup'] in ids for m in party)
    backups = sum(m['backup'] in ids for m in party)
    return represented, first, backups


def group_walk(station, spots, prefs):
    party = prefs.get('party', [])
    if not party:
        return plan_walk(station, spots, prefs)
    required = prefs['spot_ids']
    if not required:
        raise ValueError('请至少选择一个同行者想去的景点')
    base = plan_walk(station, spots, prefs)
    eligible = {s['spot_id'] for s in spots if access_point(s)} - set(prefs['skip_ids'])
    backups = sorted({m['backup'] for m in party if m['backup'] in eligible} - set(required))
    # At most four companions. Try all subsets of their optional wishes. Compare actual routes.
    best = base
    def score(plans):
        route = plans[0]['route']
        return (*_coverage(_ids(plans[0]), party), -route['total_minutes'], -route['walking_meters'])
    for count in range(1, len(backups) + 1):
        for extra in combinations(backups, count):
            try:
                plans = plan_walk(station, spots, {**prefs, 'spot_ids': required + list(extra)})
            except StationRouteConflict:
                continue
            if score(plans) > score(best):
                best = plans
    return best


def repair_choices(station, spots, prefs, allow_steps):
    start = station_anchor(station)
    by_id = {s['spot_id']: s for s in spots if access_point(s)}
    original = prefs['spot_ids']
    party = prefs.get('party', [])
    initial_exit = prefs['end_area']
    gates = {**NETWORK['gates'], 'return': start}
    choices = {}
    def record(plan, patch):
        route = plan['route']
        included = _ids(plan)
        lost = set(original) - included
        edits = len(lost) + sum(patch[k] != prefs[k] for k in ('end_area', 'avoid_steps', 'budget'))
        score = (*(-v for v in _coverage(included, party)[:2]), edits, len(lost),
                 patch['budget'] - prefs['budget'], route['total_minutes'], route['walking_meters'])
        category = ('stairs' if patch['avoid_steps'] != prefs['avoid_steps'] else
                    'time' if patch['budget'] > prefs['budget'] else 'adjust')
        if category not in choices or score < choices[category][0]:
            choices[category] = (score, dict(changes=patch, stop_ids=[s['spot_id'] for s in route['stops']],
                                              minutes=route['total_minutes'], meters=route['walking_meters']))
    modes = [prefs['avoid_steps']]
    if prefs['avoid_steps'] and allow_steps:
        modes.append(False)
    for avoid in modes:
        reachable = [i for i in original if i in by_id and math.isfinite(anchor_distance(by_id[i], start, avoid))]
        if original and not reachable:
            reachable = list(dict.fromkeys(m['backup'] for m in party if m['backup'] in by_id
                             and m['backup'] not in prefs['skip_ids'] and math.isfinite(anchor_distance(by_id[m['backup']], start, avoid))))
            if not reachable:
                continue
        exits = []
        seen = set()
        for area in dict.fromkeys([initial_exit, 'east', 'north', 'south', 'return']):
            gate = gates[area]
            if gate['node_id'] in seen or not math.isfinite(anchor_to_anchor_distance(start, gate, avoid)):
                continue
            seen.add(gate['node_id'])
            exits.append(area)
        for area in exits:
            ids = reachable[:]
            # For a tight budget, remove one stop per pass. Protect people's wishes first;
            # use actual visit and adjacent walking minutes to choose among equivalent removals.
            pending = [ids]
            examined = set()
            while pending:
                ids = pending.pop()
                key = tuple(ids)
                if key in examined:
                    continue
                examined.add(key)
                patch = dict(end_area=area, avoid_steps=avoid, budget=prefs['budget'], spot_ids=ids)
                try:
                    plan = group_walk(station, spots, {**prefs, **patch})[0]
                    record(plan, patch)
                    continue
                except StationBudgetConflict as exc:
                    route = exc.route
                    needed = route['total_minutes']
                    if needed <= 480 and not prefs.get('exit_by'):
                        extended = {**patch, 'budget': needed}
                        plan = (group_walk(station, spots, {**prefs, **extended})[0]
                                if party or prefs.get('fill_time') else {'route': route})
                        record(plan, extended)
                    if party and len(ids) <= 4:
                        # Up to four first choices: evaluate each smaller group before deciding
                        # whose primary can be replaced by their backup within the time budget.
                        pending.extend(list(subset) for subset in combinations(ids, len(ids)-1) if subset)
                        if len(ids) == 1:
                            pending.extend([m['backup']] for m in party if m['backup'] in by_id
                                           and m['backup'] not in prefs['skip_ids']
                                           and math.isfinite(anchor_distance(by_id[m['backup']], start, avoid)))
                        continue
                    stops = route['stops']
                    legs = [route['entry_leg'], *route['legs'], route['exit_leg']]
                    def removal_key(index):
                        i = stops[index]['spot_id']
                        remaining = set(ids) - {i}
                        return (*_coverage(remaining, party)[:2], stops[index]['visit_minutes'] +
                                legs[index]['minutes'] + legs[index+1]['minutes'])
                    drop = stops[max(range(len(stops)), key=removal_key)]['spot_id']
                    smaller = [i for i in ids if i != drop]
                    if smaller:
                        pending.append(smaller)
                except StationRouteConflict:
                    if not original and not prefs.get('exit_by'):
                        # With no pinned stops the shortest feasible single visit bounds
                        # the minimum budget for automatic recommendation.
                        candidates = [route_overview([dict(s, visit_duration=prefs['dwell_minutes'].get(i, s.get('visit_duration')))],
                                      start_anchor=start, end_anchor=gates[area], pace=prefs['pace'], avoid_steps=avoid)
                                      for i, s in by_id.items() if i not in prefs['skip_ids']]
                        needed = min((r['total_minutes'] for r in candidates if r['complete']), default=481)
                        if prefs['budget'] < needed <= 480:
                            extended = {**patch, 'budget': needed}
                            record(group_walk(station, spots, {**prefs, **extended})[0], extended)
            # Keep the requested exit when it already gives a zero-loss result under this mode.
            if area == initial_exit and any(c['changes']['end_area'] == area and
                    c['changes']['avoid_steps'] == avoid and c['changes']['budget'] == prefs['budget']
                    and set(original).issubset(c['stop_ids']) for _, c in choices.values()):
                break
    return [c for _, c in sorted(choices.values(), key=lambda item: item[0])]
