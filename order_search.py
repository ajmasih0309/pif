"""Shared, read-only search and type filters for the order views."""

import re
import unicodedata


ORDER_TYPES = (
    ('all', 'All'),
    ('public', 'Public'),
    ('pedal-partner', 'Pedal Partner'),
    ('speciality', 'Speciality'),
)


def normalize_text(value):
    if str(value).isascii():
        return str(value).casefold()
    text = unicodedata.normalize('NFKD', str(value)).casefold()
    return ''.join(char for char in text if not unicodedata.combining(char))


def canonical_order_type(value):
    value = (value or '').strip()
    return {
        '': 'Public', 'public': 'Public', 'pedal partner': 'Pedal Partner',
        'specialty': 'Speciality', 'speciality': 'Speciality',
    }.get(value.casefold(), value)


def search_orders(items, query='', order_type='all'):
    """Match all words across fields, then apply an exact order-type filter.

    Search the full result set before tab grouping or table pagination. Raw
    values (ISO dates, unformatted phones, audit fields) and displayed values
    are both indexed by fetch_all_orders. No query text is executed as SQL.
    """
    query = query.strip()
    selected_type = order_type if order_type in dict(ORDER_TYPES) else 'all'
    normalized = normalize_text(query)
    tokens = re.findall(r'[^\W_]+', normalized) or ([normalized] if normalized else [])
    exact_id = re.fullmatch(r'#(\d+)', query)
    matches = []
    for item in items:
        if exact_id:
            match = item['order_id'] == int(exact_id.group(1))
        else:
            haystack = item['_search_text']
            match = all(token in haystack for token in tokens)
        if match:
            matches.append(item)

    type_counts = {'all': len(matches)}
    for key, label in ORDER_TYPES[1:]:
        type_counts[key] = sum(item['order_type'] == label for item in matches)
    if selected_type != 'all':
        label = dict(ORDER_TYPES)[selected_type]
        matches = [item for item in matches if item['order_type'] == label]
    return matches, {
        'search_query': query,
        'selected_order_type': selected_type,
        'order_type_options': ORDER_TYPES,
        'type_counts': type_counts,
        'result_count': len(matches),
        'total_count': len(items),
        'filters_active': bool(query or selected_type != 'all'),
    }
