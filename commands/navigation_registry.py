import uuid

navigation_map = {}

def register_path(path):
    key = uuid.uuid4().hex[:8]
    navigation_map[key] = path
    return key

def get_path(key):
    return navigation_map.get(key)