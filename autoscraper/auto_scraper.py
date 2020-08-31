import os
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup


class AutoScraper(object):
    request_headers = {
        'User-Agent': 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; \
            Googlebot/2.1; +http://www.google.com/bot.html) Safari/537.36'
    }

    def __init__(self, stack_list=None, url=None):
        self.stack_list = stack_list
        self.url = url

    @staticmethod
    def _get_soup(url=None, html=None, request_args=None):
        if html:
            return BeautifulSoup(html, 'lxml')
        request_args = request_args if request_args else {}
        headers = request_args.get('headers', AutoScraper.request_headers)
        html = requests.get(url, headers=headers, **request_args).text
        return BeautifulSoup(html, 'lxml')

    @staticmethod
    def _get_valid_attrs(item):
        attrs = dict(item.attrs)
        for attr in item.attrs:
            if attr not in {'class', 'style'}:
                del attrs[attr]
                continue
            if attrs[attr] == []:
                attrs[attr] = ''
        return attrs

    def _child_has_text(self, child, text):
        child_text = child.getText().strip().rstrip()
        if text == child_text:
            child.wanted_attr = None
            return True

        for key, value in child.attrs.items():
            if not isinstance(value, str):
                continue

            value = value.strip().rstrip()
            if text == value:
                child.wanted_attr = key
                return True

            if key in {'href', 'src'}:
                full_url = urljoin(self.url, value)
                if text == full_url:
                    child.wanted_attr = key
                    child.is_full_url = True
                    return True
        return False

    def _get_children(self, soup, text):
        text = text.strip().rstrip()
        children = reversed(soup.findChildren())
        children = list(
            filter(lambda x: self._child_has_text(x, text), children))
        return children

    @staticmethod
    def unique(item_list):
        unique_list = []
        for item in item_list:
            if item not in unique_list:
                unique_list.append(item)
        return unique_list

    def build(self, url=None, wanted_list=None, html=None, request_args=None):
        self.url = url
        soup = self._get_soup(url=url, html=html, request_args=request_args)

        result_list = []
        stack_list = []

        for wanted in wanted_list:
            children = self._get_children(soup, wanted)

            for child in children:
                result, stack = self._get_result_for_child(child, soup)
                result_list += result
                stack_list.append(stack)

        result_list = self.unique(result_list)

        if self._check_result(result_list, wanted_list):
            self.stack_list = self.unique(stack_list)
            return result_list

        return None

    @staticmethod
    def _check_result(result, wanted_list):
        for w in wanted_list:
            if w not in result:
                return False
        return True

    @staticmethod
    def _build_stack(child):
        content = [(child.name, AutoScraper._get_valid_attrs(child))]

        parent = child
        while True:
            grand_parent = parent.findParent()
            if not grand_parent:
                break

            for i, c in enumerate(grand_parent.findAll(parent.name, recursive=False)):
                if c == parent:
                    content.insert(
                        0, (grand_parent.name, AutoScraper._get_valid_attrs(grand_parent), i))
                    break
            if grand_parent.name == 'html':
                break
            parent = grand_parent

        wanted_attr = getattr(child, 'wanted_attr', None)
        is_full_url = getattr(child, 'is_full_url', False)
        stack = dict(content=content, wanted_attr=wanted_attr,
                     is_full_url=is_full_url)
        return stack

    def _get_result_for_child(self, child, soup):
        stack = AutoScraper._build_stack(child)
        result = self._get_result_with_stack(stack, soup)
        return result, stack

    def _fetch_result_from_child(self, child, wanted_attr, is_full_url):
        if wanted_attr is None:
            return child.getText().strip().rstrip()
        if is_full_url:
            return urljoin(self.url, child.attrs[wanted_attr])
        return child.attrs[wanted_attr]

    def _get_result_with_stack(self, stack, soup):
        parents = [soup]
        for _, item in enumerate(stack['content']):
            children = []
            for parent in parents:
                children += parent.findAll(item[0], item[1], recursive=False)
            parents = children

        wanted_attr = stack['wanted_attr']
        is_full_url = stack['is_full_url']
        result = [self._fetch_result_from_child(
            i, wanted_attr, is_full_url) for i in parents]
        result = list(filter(lambda x: x, result))
        return result

    def _get_result_with_stack_index_based(self, stack, soup):
        p = soup.findChildren(recursive=False)[0]
        stack_content = stack['content']
        for index, item in enumerate(stack_content[:-1]):
            p = p.findAll(stack_content[index + 1]
                          [0], recursive=False)[item[2]]
        result = self._fetch_result_from_child(
            p, stack['wanted_attr'], stack['is_full_url'])
        return result

    def get_result_similar(self, url=None, html=None, soup=None, request_args=None):
        if url:
            self.url = url
        if not soup:
            soup = self._get_soup(url=url, html=html,
                                  request_args=request_args)
        result = []
        for stack in self.stack_list:
            result += self._get_result_with_stack(stack, soup)
        return self.unique(result)

    def get_result_exact(self, url=None, html=None, soup=None, request_args=None):
        if url:
            self.url = url
        if not soup:
            soup = self._get_soup(url=url, html=html,
                                  request_args=request_args)
        result = []
        for stack in self.stack_list:
            try:
                result.append(
                    self._get_result_with_stack_index_based(stack, soup))
            except IndexError as e:
                print(e)
        return self.unique(result)

    def get_result(self, url=None, html=None, request_args=None):
        soup = self._get_soup(url=url, html=html, request_args=request_args)
        similar = self.get_result_similar(soup=soup)
        exact = self.get_result_exact(soup=soup)
        return similar, exact

    def generate_python_code(self):
        file_path = os.path.join(os.path.dirname(__file__), "code_template.py")
        with open(file_path, 'r') as f:
            code = f.read()
        code = code.replace('"{STACK_LIST}"', str(self.stack_list))
        print(code)
