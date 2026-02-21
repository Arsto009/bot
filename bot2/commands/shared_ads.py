# هذا ملف وسيط لكسر التعارض بين menu و menu_extra

ad_message_map = {}

def get_node(categories, path):
    node = {"sub": categories}
    for key in path.split("/"):
        if not key:
            continue
        node = node["sub"].get(key)
        if not node:
            return None
    return node