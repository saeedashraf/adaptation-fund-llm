# INPUTS
INPUT_FILE = "input_links.txt"
DATABASE_NAME = "AdaptationFund_Database.db"
BATCH_SIZE = 1 # how many parallel requests
# END OF INPUTS

# install: requests, lxml, openpyxl
import requests
from lxml import html
from openpyxl import Workbook
import os
import sys
import bz2
import sqlite3
import pickle
import json
import pprint
import time
from datetime import datetime
import threading
import random


class AdaptationFund_Scraper:
    def __init__(self, input_filename, input_databasename, input_batchsize, read_inputs=True):
        ## check if inputs are good
        self.inputs_are_good = True
        self.is_interrupted = False

        input_checks = [self.check_input('INPUT_FILE', 'str', input_filename),
                        self.check_input('DATABASE_NAME', 'str', input_databasename),
                        self.check_input('BATCH_SIZE', 'positive_int', input_batchsize)]
        if False in input_checks:
            print("Bad inputs, quit!")
            self.inputs_are_good = False
            return

        ## if still here, set inputs
        self.input_file = input_filename
        self.database_name = input_databasename
        self.batch_size = input_batchsize

        ## create database
        if not os.path.exists(self.database_name):
            print("Creating a new database...")
        else:
            print("Database already exists!")
        self.db_conn = sqlite3.connect(self.database_name, check_same_thread=False)
        self.db_cursor = self.db_conn.cursor()
        self.db_cursor.execute("CREATE TABLE IF NOT EXISTS Projects(project_url TEXT NOT NULL PRIMARY KEY, project_name TEXT, html BLOB, time_of_scraping TEXT, timestamp REAL, files_json BLOB, number_of_files INTEGER)")
        self.db_cursor.execute("CREATE TABLE IF NOT EXISTS Files(file_url TEXT NOT NULL PRIMARY KEY, file_name TEXT, content BLOB, content_type BLOB)")

        ## other
        self.good_count = 0
        self.LOCK = threading.Lock()

        ## read inputs
        if read_inputs == True:
            self.input_links = self.read_input_links()
            print("Unique input links read:", len(self.input_links))
        
        return


    def read_input_links(self):
        ## return a list of unique input links
        unique_links = {}
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                for line in f:
                    potential_link = line.strip()
                    if potential_link.lower().startswith("https:") or potential_link.lower().startswith("http:"):
                        if potential_link not in unique_links:
                            unique_links[potential_link] = ''
                            
        except Exception as input_exc:
            print("An exception while reading inputs:", repr(input_exc))
            unique_links = {} # reset

        return [{"url":uniquelink} for uniquelink in unique_links]


    def scrape_html(self):
        if self.inputs_are_good == False or self.is_interrupted == True:
            return

        # insert all input links into the database
        for input_item in self.input_links:
            self.db_cursor.execute("INSERT OR IGNORE INTO Projects(project_url) VALUES(?)", (input_item["url"],))
        self.db_conn.commit()

        # scrape needed items
        items_to_scrape = []
        for input_item in self.input_links:
            existence_check = self.db_cursor.execute("SELECT EXISTS(SELECT 1 FROM Projects WHERE project_url=? AND html IS NOT NULL)", (input_item["url"],)).fetchone()[0]
            if existence_check == 1:
                continue
            else:
                items_to_scrape.append(input_item)

        print("Projects left to scrape:", len(items_to_scrape))
        self.scrape_threaded_from_list(items_to_scrape, self.html_thread, "project")
        return


    def html_thread(self, input_dict):
        data_to_save = {"html":None, "project_name":None, "files":[], "good_to_save":False}
        try:
            r = requests.get(input_dict["url"], timeout=30)
            tree = html.fromstring(r.text)

            # find project name, need it for folders
            projectname_el = tree.xpath("./body/div[@id='wrapper']/div[contains(@class, 'fusion-page-title')]//h1[contains(@class, 'entry-title')]")
            if len(projectname_el) != 0:
                data_to_save["html"] = bz2.compress(pickle.dumps(r.text))
                data_to_save["project_name"] = projectname_el[0].text_content().strip()

            # get files, not mandatory
            file_els = tree.xpath("./body/div[@id='wrapper']//div[contains(@id, 'post-')]//h3[contains(text(), 'Project Documents')]/following-sibling::table[contains(@class, 'dataTable')][1]//tr")
            for file_el in file_els: # these are tr elements
                url_els = file_el.xpath("./td/a[@href]")
                if len(url_els) != 0:
                    data_to_save["files"].append({"file_url":url_els[0].attrib["href"], "file_name":url_els[0].text_content().strip() })

            # see if good to save
            if data_to_save["html"] != None and data_to_save["project_name"] != None:
                data_to_save["good_to_save"] = True
        except:
            pass

        # save if good
        with self.LOCK:
            try:
                if data_to_save["good_to_save"] == True:
                    current_time_object = datetime.now()
                    for file_to_insert in data_to_save["files"]:
                        self.db_cursor.execute("INSERT OR IGNORE INTO Files(file_url, file_name) VALUES(?,?)", (file_to_insert["file_url"], file_to_insert["file_name"]))
                    self.db_cursor.execute("UPDATE Projects SET project_name=?, html=?, time_of_scraping=?, timestamp=?, files_json=?, number_of_files=? WHERE project_url=?",
                                           (data_to_save["project_name"], data_to_save["html"], current_time_object.strftime("%d-%B-%Y"), current_time_object.timestamp(),
                                            json.dumps([fileitem["file_url"] for fileitem in data_to_save["files"]]), len(data_to_save["files"]), input_dict["url"] ))
                    self.db_conn.commit()
                    self.good_count+=1
                else:
                    print("Couldn't verify scrape for", input_dict["url"])
            except:
                pass
            
        return



    def download_documents(self):
        if self.inputs_are_good == False or self.is_interrupted == True:
            return

        items_to_scrape = [{"file_url":x[0]} for x in self.db_cursor.execute("SELECT file_url FROM Files WHERE content IS NULL").fetchall()]
        print("Files left to scrape:", len(items_to_scrape))
        #random.shuffle(items_to_scrape) # for testing, can remove later
        self.scrape_threaded_from_list(items_to_scrape, self.file_download_func, "file")
        return


    def file_download_func(self, input_dict):
        data_to_save = {"content":None, "content_type":None}
        try:
            r = requests.get(input_dict["file_url"], timeout=120)
            if r.status_code in [200, 302]:
                data_to_save["content_type"] = r.headers["Content-Type"].lower().strip()
                data_to_save["content"] = r.content
        except:
            pass

        # save if good
        with self.LOCK:
            try:
                if data_to_save["content"] != None:
                    self.db_cursor.execute("UPDATE Files SET content=?, content_type=? WHERE file_url=?", (data_to_save["content"], data_to_save["content_type"], input_dict["file_url"] ))
                    self.db_conn.commit()
                    self.good_count+=1
                else:
                    print("Couldn't verify file download for", input_dict["file_url"])
            except:
                pass
        
        return
    
    


    def scrape_threaded_from_list(self, input_list, input_thread_func, input_print_string, max_items=None, batch_size=None):
        all_thread_items = []
        self.good_count = 0

        if batch_size == None:
            relevant_batch_size = self.batch_size
        else:
            relevant_batch_size = batch_size
            
        for input_index, input_item in enumerate(input_list):
            if type(max_items) == int:
                if input_index == max_items:
                    break # maximum reached
            
            all_thread_items.append(input_item)
            if len(all_thread_items) == relevant_batch_size:
                ## call it
                all_threads = []
                for a_thread_item in all_thread_items:
                    current_thread = threading.Thread(target=input_thread_func, args=(a_thread_item, ))
                    all_threads.append(current_thread)
                    current_thread.start()

                for thr in all_threads:
                    thr.join()
                    
                print("Current", input_print_string, "item number", input_list.index(input_item)+1, "/", len(input_list),
                      "Good requests in this batch:", self.good_count, "/", len(all_thread_items))
                self.good_count = 0
                all_thread_items = []


        if len(all_thread_items) != 0:
            ## call for residuals
            all_threads = []
            for a_thread_item in all_thread_items:
                current_thread = threading.Thread(target=input_thread_func, args=(a_thread_item, ))
                all_threads.append(current_thread)
                current_thread.start()

            for thr in all_threads:
                thr.join()
                
            print("Current", input_print_string, "item number", input_list.index(input_item)+1, "/", len(input_list),
                  "Good requests in this batch:", self.good_count, "/", len(all_thread_items))
            self.good_count = 0
            all_thread_items = []
            
        return
    

    def check_input(self, input_name, input_type, input_value):
        input_is_good = True
        if input_type == 'str':
            if type(input_value) != str:
                input_is_good = False
                print(input_name + " should be a string!")
        elif input_type == 'positive_int':
            if type(input_value) != int:
                input_is_good = False
                print(input_name + " should be an integer!")
            else:
                if input_value <= 0:
                    input_is_good = False
                    print(input_name + " should be a positive integer!")
        else:
            print("Unhandled input type: " + input_type)
            
        return input_is_good



if __name__ == '__main__':
    scraper_instance = AdaptationFund_Scraper(INPUT_FILE, DATABASE_NAME, BATCH_SIZE)
    scraper_instance.scrape_html()
    scraper_instance.download_documents()
