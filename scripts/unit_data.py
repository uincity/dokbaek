"""Shared validation for small stages; no workbook/browser dependencies."""
from datetime import date
from pathlib import PurePosixPath
import re


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_units(events, songs, members, approved_media=()):
    require(isinstance(events, list), 'Small stages: expected an event array')
    song_ids = {s['id'] for s in songs}
    member_names = {m['id']: m['nickname'] for m in members}
    ids, categories = set(), set()
    for event in events:
        label = f"Small stage {event.get('id', '?')}"
        require(not set(event) - {'id', 'source_category', 'title', 'type', 'date', 'venue', 'source_venue', 'status', 'songs', 'description', 'media', 'notes'}, f'{label}: unsupported fields')
        for field in ('id', 'source_category', 'title', 'type', 'date', 'venue', 'source_venue'):
            require(text(event.get(field)), f'{label}: missing {field}')
        require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', event['id']), f'{label}: unsafe ID')
        require(event['id'] not in ids, f'{label}: duplicate event ID')
        require(event['source_category'] not in categories, f'{label}: duplicate source category')
        ids.add(event['id']); categories.add(event['source_category'])
        require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', event['date']), f'{label}: invalid date')
        date.fromisoformat(event['date'])
        require(event.get('status') in {'scheduled', 'completed'}, f'{label}: invalid status')
        for field in ('description', 'notes'):
            require(field not in event or text(event[field]), f'{label}: empty {field}')
        require(isinstance(event.get('songs'), list) and event['songs'], f'{label}: empty program')
        orders = set()
        for song in event['songs']:
            require(not set(song) - {'order', 'title', 'song_id', 'source_title', 'source_performers', 'formats', 'performers'}, f'{label}: unsupported song fields')
            require(type(song.get('order')) is int and song['order'] > 0 and song['order'] not in orders, f'{label}: duplicate/invalid program order')
            orders.add(song['order'])
            for field in ('title', 'source_title', 'source_performers'):
                require(text(song.get(field)), f'{label}: missing {field}')
            require('song_id' in song and (song['song_id'] is None or song['song_id'] in song_ids), f'{label}: unknown song ID')
            require(isinstance(song.get('formats'), list) and all(text(f) for f in song['formats']), f'{label}: invalid formats')
            require(isinstance(song.get('performers'), list) and song['performers'], f'{label}: missing performers')
            seen = set()
            for performer in song['performers']:
                require(set(performer) == {'member_id', 'name', 'roles'}, f'{label}: invalid performer fields')
                member_id = performer['member_id']
                require(member_id in member_names and performer['name'] == member_names[member_id], f'{label}: missing/unknown member name')
                require(member_id not in seen, f'{label}: duplicate performer')
                seen.add(member_id)
                roles = performer['roles']
                require(isinstance(roles, list) and roles and all(text(r) for r in roles) and len(roles) == len(set(roles)), f'{label}: missing/duplicate roles')
        require('media' not in event or isinstance(event['media'], list), f'{label}: invalid media array')
        for media in event.get('media', []):
            require({'type', 'label', 'path', 'reviewed'} <= set(media) <= {'type', 'label', 'path', 'reviewed', 'usage', 'width', 'height'}, f'{label}: invalid media fields')
            require(media['type'] in {'image', 'video'} and media['reviewed'] is True and text(media['label']), f'{label}: media needs explicit public approval')
            require(media['path'] in approved_media, f'{label}: media needs public allowlist review')
            suffix = PurePosixPath(media['path']).suffix.lower()
            require(suffix in ({'.mp4', '.webm'} if media['type'] == 'video' else {'.jpg', '.jpeg', '.png', '.webp'}), f'{label}: media type/extension mismatch')
            if 'usage' in media:
                require(media['type'] == 'image' and media['usage'] in {'sketch', 'poster'}, f'{label}: invalid image usage')
            if 'width' in media or 'height' in media:
                require(all(type(media.get(key)) is int and media[key] > 0 for key in ('width', 'height')), f'{label}: invalid image dimensions')
    return events
