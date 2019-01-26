import argparse
import asyncio

from models import db_session, Page

from aiohttp import ClientSession
from lxml import html
from urllib.parse import unquote


URL = 'https://ru.wikipedia.org/{}'
SEMA = asyncio.BoundedSemaphore(1000)
OFFTOP = ['Служебная:', 'Википедия:', 'Портал:', 'Категория:', 'Файл:', 'Проект:', 'Шаблон:', 'Обсуждение:']


async def fetch(url, session):
    async with session.get(url) as response:
        return await response.read()


def is_valid_ref(ref, db_session):
    is_wiki = ref.startswith('/wiki')
    page_exists = db_session.query(Page).filter_by(url=URL.format(ref)).count()
    not_offtop = not any(substring in ref for substring in OFFTOP)

    return is_wiki and not page_exists and not_offtop


async def parse(article, session, recursion_depth, from_page_id, limit_rd=1):
    async with SEMA:
        global URL
        task = [asyncio.ensure_future(fetch(URL.format(article), session))]
        response = await asyncio.gather(*task)
        data = html.fromstring(response[0])
        anchors = data.xpath('//a[@title]')

        entities = []
        for anchor in anchors:
            href = unquote(anchor.attrib['href'])
            # проверить, что урл начинается с /wiki, а также этот урл не повторяется в БД
            if not is_valid_ref(href, db_session) or 'страница отсутствует' in anchor.attrib['title']:
                continue

            page = Page(url=URL.format(href), from_page_id=from_page_id)
            db_session.add(page)
            db_session.commit()
            db_session.refresh(page)
            entities.append((page.id, href))

        # Если дошли до конца рекурсии, останавливаемся
        if recursion_depth > limit_rd:
            return

        # Создаем новый ивент-луп под полученные ссылки, и также рекурсивно запускаем эту функцию под них
        subtasks = []
        for page_id, page_url in entities:
            subtasks.append(asyncio.ensure_future(parse(page_url, session, recursion_depth + 1, page_id)))
        await asyncio.gather(*subtasks)


async def run(article, limit_rd):
    global URL
    async with ClientSession() as session:
        page = Page(url=URL.format(article))
        db_session.add(page)
        db_session.commit()
        db_session.refresh(page)
        main_task = [asyncio.ensure_future(parse(article, session, 0, from_page_id=page.id, limit_rd=limit_rd))]
        await asyncio.gather(*main_task)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--article', dest='article', type=str, required=True)
    parser.add_argument('-r', '--limit_rd', dest='limit_rd', type=int, default=1)
    args = parser.parse_args()

    article = args.article
    limit_rd = args.limit_rd

    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(run(f"wiki/{article}", limit_rd))
    loop.run_until_complete(future)
