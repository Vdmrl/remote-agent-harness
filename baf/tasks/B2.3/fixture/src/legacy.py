from datetime import datetime
def parse_date(text):
    return datetime.strptime(text, '%Y-%m-%d')
