import re
from urllib import request

from bs4 import BeautifulSoup as parse
from bs4.element import Tag

from parsers.canteen import Meal, Entry, Category
from pyopenmensa.feed import OpenMensaCanteen, buildLegend
from utils import Parser


def parse_url(url, today=False):
    raw_html = request.urlopen(url).read()
    document = parse(raw_html, 'lxml')
    return parse_html_document(document)


def parse_html_document(document):
    canteen = OpenMensaCanteen()
    # todo only for: Tellergericht, vegetarisch, Klassiker, Empfehlung des Tages:
    canteen.setAdditionalCharges('student', {'other': 1.5})
    # unwanted automatic notes extraction would be done in `OpenMensaCanteen.addMeal()`
    # if we used `LazyBuilder.setLegendData()`, so we bypass it using a custom attribute
    canteen.legend = parse_legend(document)

    parse_all_days(canteen, document)

    return canteen.toXMLFeed()


def parse_legend(document):
    regex = '\((?P<name>[\dA-Z]+)\)\s*(?P<value>[\w\s]+)'
    return buildLegend(text=document.find(id='additives').text, regex=regex)


def parse_all_days(canteen, document):
    days = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag',
            'MontagNaechste', 'DienstagNaechste', 'MittwochNaechste', 'DonnerstagNaechste',
            'FreitagNaechste')
    for day in days:
        day_column = document.find('div', id=day)
        if day_column is None:  # assume closed?
            continue
        day_header = day_column.find_previous_sibling('h3')
        parse_day(canteen, day_header.text, day_column)


def parse_day(canteen, day, day_container):
    if is_closed(day_container):
        canteen.setDayClosed(day)
        return

    meals_table = day_container.find(attrs={'class': 'menues'})
    meal_entries = parse_all_entries_from_table(meals_table)

    extras_table = day_container.find(attrs={'class': 'extras'})
    extras_entries = parse_all_entries_from_table(extras_table)

    all_entries = meal_entries + extras_entries
    for entry in all_entries:
        if entry.category.name and entry.meal.name:
            canteen.addMeal(
                day,
                entry.category.name,
                entry.meal.name,
                entry.meal.get_fulltext_notes(canteen.legend),
                prices=entry.category.price)


def is_closed(data):
    note = data.find(id='note')
    if note:
        return True
    else:
        return False


def parse_all_entries_from_table(table):
    all_entries = []
    for item in table.find_all('tr'):
        entry = parse_entry(item)
        all_entries.append(entry)

    return all_entries


def parse_entry(table_row):
    category = parse_category(table_row)

    meal_container = table_row.find('span', attrs={'class': 'menue-desc'})
    meal = parse_meal(meal_container)

    return Entry(category, meal)


def parse_category(category_container):
    category_name = category_container.find('span', attrs={'class': 'menue-category'}).text.strip()

    category = Category(category_name)

    price_element = category_container.find('span', attrs={'class': 'menue-price'})
    if price_element:
        price_string = price_element.text.strip()
        category.set_price_from_string(price_string)

    return category


def parse_meal(meal_container):
    clean_meal_container = get_cleaned_meal_container(meal_container)

    name_parts = []
    notes = set()

    for element in clean_meal_container:
        if type(element) is Tag and element.name == 'sup':
            notes.update(element.text.strip().split(','))
        else:
            name_parts.append(element.string.strip())
    name = re.sub(r"\s+", ' ', ' '.join(name_parts))

    meal = Meal(name)
    meal.set_note_keys(notes)
    return meal


def get_cleaned_meal_container(meal_container):
    # "Hauptbeilage" and "Nebenbeilage" are flat,
    # while the others are wrapped in <span class="expand-nutr">
    effective_meal_container = meal_container.find('span', attrs={
        'class': 'expand-nutr'}) or meal_container

    def is_valid_meal_element(element):
        if not isinstance(element, Tag):
            return True
        # Keep <span class="seperator">oder</span>, notice typo in "seperator"
        if element.name == 'span' and 'seperator' in element['class']:
            # Sometimes it's empty, i. e. <span class="seperator"></span>
            return len(element.contents) > 0
        # Keep <sup> tags for notes
        if element.name == 'sup':
            return True
        return False

    meal_container = list(filter(
        is_valid_meal_element,
        effective_meal_container.children
    ))

    return meal_container


parser = Parser(
    'aachen',
    handler=parse_url,
    shared_prefix='http://www.studierendenwerk-aachen.de/speiseplaene/',
)

parser.define('academica', suffix='academica-w.html')
parser.define('ahorn', suffix='ahornstrasse-w.html')
parser.define('templergraben', suffix='templergraben-w.html')
parser.define('bayernallee', suffix='bayernallee-w.html')
parser.define('eups', suffix='eupenerstrasse-w.html')
parser.define('goethe', suffix='goethestrasse-w.html')
parser.define('vita', suffix='vita-w.html')
parser.define('zeltmensa', suffix='forum-w.html')
parser.define('juelich', suffix='juelich-w.html')
