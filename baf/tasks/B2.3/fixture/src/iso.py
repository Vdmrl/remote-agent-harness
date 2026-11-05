from datetime import datetime
def parse_date(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))
