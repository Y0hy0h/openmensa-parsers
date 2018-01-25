import re
from urllib import request

from bs4 import BeautifulSoup as parse
from bs4.element import Tag

from parsers.canteen import Meal, Entry, Category
from pyopenmensa.feed import OpenMensaCanteen, buildLegend
from utils import Parser


def parse_url(url, today=False):
    document = parse(request.urlopen(url).read(), 'lxml')
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


def parse_day(canteen, day, data):
    if is_closed(data):
        canteen.setDayClosed(day)
        return

    meals_table = data.find(attrs={'class': 'menues'})
    add_meals_from_table(canteen, meals_table, day)

    extras_table = data.find(attrs={'class': 'extras'})
    add_meals_from_table(canteen, extras_table, day)


def is_closed(data):
    note = data.find(id='note')
    if note:
        return True
    else:
        return False


def add_meals_from_table(canteen, table, day):
    for item in table.find_all('tr'):
        entry = parse_entry(item)
        if entry.category.name and entry.meal.name:
            canteen.addMeal(
                day,
                entry.category.name,
                entry.meal.name,
                entry.meal.get_fulltext_notes(canteen.legend),
                prices=entry.category.price)


def parse_entry(table_row):
    category = parse_category(table_row)

    meal_container = table_row.find('span', attrs={'class': 'menue-desc'})
    clean_meal_container = get_cleaned_meal_container(meal_container)
    meal = parse_meal(clean_meal_container)

    return Entry(category, meal)


def parse_category(table_row):
    category_name = table_row.find('span', attrs={'class': 'menue-category'}).text.strip()
    category = Category(category_name)
    price_element = table_row.find('span', attrs={'class': 'menue-price'})
    if price_element:
        price_string = price_element.text.strip()
        category.set_price_from_string(price_string)
    return category


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


def parse_meal(description_container):
    name_parts = []
    notes = set()

    for element in description_container:
        if type(element) is Tag and element.name == 'sup':
            notes.update(element.text.strip().split(','))
        else:
            name_parts.append(element.string.strip())
    name = re.sub(r"\s+", ' ', ' '.join(name_parts))

    meal = Meal(name)
    meal.set_note_keys(notes)
    return meal


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
