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


class Task(ndb.Model):
    url = ndb.StringProperty()
    title = ndb.StringProperty()
    description = ndb.StringProperty()
    image = ndb.StringProperty()
    board = ndb.StringProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)


class MainHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {
            'app_name': "VookMark"
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

        new_description = self.request.get("description")
        if new_description:
            task.description = new_description
            task.put()

        self.redirect("/board?id=" + board)


class BoardHandler(webapp2.RequestHandler):
    def get(self):
        board_id = self.request.get("id")

        qry = Task.query(Task.board == board_id).order(-Task.created)
        tasks = qry.fetch(100)

        template_values = {
            'board_id': board_id,
            'tasks': tasks,
        }
        template = JINJA_ENVIRONMENT.get_template('board.html')
        self.response.write(template.render(template_values))


class BoardHandlerOld(webapp2.RequestHandler):
    def get(self):
        board_id = self.request.get("id")

        qry = Task.query(Task.board == board_id).order(-Task.created)
        tasks = qry.fetch(100)
        tasks_html = ""
        for task in tasks:
            desc = task.description
            if desc is None:
                desc = "Edit"
            tasks_html = tasks_html + "<a href=/task?id=" + str(task.key.id()) \
                         + "><h3>" + desc + "</h3>" \
                         + task.title \
                         + "<img src=" + task.image + " height='250' ></a>"

        self.response.write(
            """
            Welcome to board """ + board_id + """<br>
            Drag this link: <a href="javascript:void(window.open('http://vookmark.appspot.com/addtask?board="""
            + board_id + """&url='+location.href, '_blank'))">+""" + board_id + """</a>
            to your bookmark bar<br>click it when visiting an interesting page to create a task.
            """
            + tasks_html
        )


class TaskMaker(webapp2.RequestHandler):
    def get(self):
        url = self.request.get("url")
        board = self.request.get("board")
        existing_task = Task.query(Task.url == url).get()
        existing_task_in_board = Task.query(Task.url == url, Task.board == board).get()

        if existing_task_in_board:
            logging.error('existing_task_in_board')
            self.redirect("/board?id=" + board)
            return

        if existing_task:
            logging.error('existing_task')
            entity = Task(url=url, title=existing_task.title, image=existing_task.image, board=board)
            entity.put()
            self.redirect("/board?id=" + board)
            return

        logging.error('not_existing_task')
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

        entity = Task(url=url, title=title, image=image, board=board)
        entity.put()
        self.redirect("/board?id=" + board)


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return int(mktime(obj.timetuple()))

        return json.JSONEncoder.default(self, obj)


app = webapp2.WSGIApplication(
    [('/', MainHandler), ('/board', BoardHandler), ('/api/board', BoardJson), ('/addtask', TaskMaker),
     ('/edittask', TaskEdit),
     ('/task', TaskView)], debug=True)
