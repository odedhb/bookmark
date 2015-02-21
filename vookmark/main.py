import Cookie
import calendar
import logging
from time import mktime
import urllib2
import urlparse
import json
import datetime
from google.appengine.ext import ndb
import webapp2
from bs4 import BeautifulSoup
import os

import jinja2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

APP_NAME = "VookMark"


class Task(ndb.Model):
    url = ndb.StringProperty()
    title = ndb.StringProperty()
    description = ndb.StringProperty()
    image = ndb.StringProperty()
    board = ndb.StringProperty()
    done = ndb.BooleanProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)


class MainHandler(webapp2.RequestHandler):
    def get(self):
        recent_boards = self.request.cookies

        template_values = {
            'app_name': APP_NAME,
            'recent_boards': recent_boards
        }
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))


class BoardJson(webapp2.RequestHandler):
    def get(self):
        board_id = self.request.get("id")

        qry = Task.query(Task.board == board_id).order(-Task.created)
        tasks = qry.fetch(20)
        self.response.headers['Content-Type'] = 'application/json'
        obj = [p.to_dict() for p in tasks]
        j = json.dumps(obj, cls=MyEncoder)
        self.response.out.write(j)


class TaskView(webapp2.RequestHandler):
    def get(self):
        task_id = self.request.get("id")
        task = Task.get_by_id(int(task_id))

        template_values = {
            'task': task,
            'task_id': task_id
        }
        template = JINJA_ENVIRONMENT.get_template('task.html')
        self.response.write(template.render(template_values))


class TaskEdit(webapp2.RequestHandler):
    def get(self):
        task_id = self.request.get("id")
        task = Task.get_by_id(int(task_id))
        board = task.board

        move = self.request.get("move")
        if move == "delete":
            task.key.delete()
            self.redirect("/board?id=" + board)
        if move == "done":
            task.done = True
            task.put()
            self.redirect("/board?id=" + board)

        new_description = self.request.get("description")
        if new_description:
            task.description = new_description
            task.put()

        self.redirect("/board?id=" + board)


class BoardHandler(webapp2.RequestHandler):
    def get(self):
        board_id = self.request.get("id")

        self.response.set_cookie(key=board_id, value=board_id)

        qry1 = Task.query(Task.board == board_id)
        qry2 = qry1.order(-Task.created)

        all_tasks = qry2.fetch(100)
        tasks = []
        done_tasks = []

        for task in all_tasks:
            if task.done is True:
                done_tasks.append(task)
            else:
                tasks.append(task)

        template_values = {
            'board_id': board_id,
            'tasks': tasks,
            'done_tasks': done_tasks,
        }
        template = JINJA_ENVIRONMENT.get_template('board.html')
        self.response.write(template.render(template_values))


class BoardLessTaskMaker(webapp2.RequestHandler):
    def get(self):
        url = self.request.get("url")
        recent_boards = self.request.cookies

        template_values = {
            'app_name': APP_NAME,
            'recent_boards': recent_boards,
            'url': url
        }
        template = JINJA_ENVIRONMENT.get_template('bookmark.html')
        self.response.write(template.render(template_values))


class TaskMaker(webapp2.RequestHandler):
    def get(self):

        desc = self.request.get("desc")
        url = self.request.get("url")
        board = self.request.get("board")

        existing_task = Task.query(Task.url == url).get()
        existing_task_in_board = Task.query(Task.url == url, Task.board == board).get()

        if existing_task_in_board:
            logging.debug('existing_task_in_board')
            self.redirect("/board?id=" + board)
            return

        if existing_task:
            logging.debug('existing_task')
            entity = Task(url=url, title=existing_task.title, image=existing_task.image, board=board)
            entity.put()
            self.redirect("/board?id=" + board)
            return

        logging.debug('not_existing_task')

        if not url:
            entity = Task(board=board, description=desc)
            entity.put()
            self.redirect("/board?id=" + board)
            return

        soup = BeautifulSoup(urllib2.urlopen(url))
        title = soup.title.string
        image = None
        image_tag = soup.find('meta', attrs={'property': 'og:image', 'content': True})

        if image_tag is not None:
            image = image_tag['content']

        if image is None:
            for img in soup.find_all('img'):
                image_relative_url = img.get('src')
                image = urlparse.urljoin(url, image_relative_url)

        entity = Task(url=url, title=title, image=image, board=board, description=desc)
        entity.put()
        self.redirect("/board?id=" + board)


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return int(mktime(obj.timetuple()))

        return json.JSONEncoder.default(self, obj)


app = webapp2.WSGIApplication(
    [('/', MainHandler), ('/board', BoardHandler), ('/api/board', BoardJson), ('/addtask', TaskMaker),
     ('/edittask', TaskEdit), ('/link', BoardLessTaskMaker),
     ('/task', TaskView)], debug=True)
