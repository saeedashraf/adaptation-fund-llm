## WRITING INPUTS
SAVING_FOLDER = "adaptation_fund_files"
## END OF INPUTS


from adaptation_fund_scrape_1 import INPUT_FILE
from adaptation_fund_scrape_1 import DATABASE_NAME
from adaptation_fund_scrape_1 import BATCH_SIZE
from adaptation_fund_scrape_1 import AdaptationFund_Scraper



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
import mimetypes



class AdaptationFund_Parser(AdaptationFund_Scraper):
    def __init__(self, input_savingfolder, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # check inputs
        if type(input_savingfolder) != str:
            print("SAVING_FOLDER should be a string!")
            self.inputs_are_good = False

        if self.inputs_are_good == False:
            print("Bad writing inputs, quit!")
            return

        # set inputs
        self.saving_folder = input_savingfolder
        
        return
    
    def write_data(self):
        if self.inputs_are_good == False or self.is_interrupted == True:
            return
        
        print("Writing data...")

        # go over input links and parse data
        all_data = []
        for input_index, input_link in enumerate(self.input_links):
            parsed_data = self.fetch_and_parse_data(input_link["url"])
            #pprint.pprint(parsed_data)
            #print([key for key in parsed_data["basic"]])
            #print([key for key in parsed_data["files"][0]])

            all_data.append(parsed_data)

            if (input_index+1)%50 == 0:
                print("Item scraped so far:", input_index+1)
                #break # remove

        # write data
        basic_headers = ['Project URL', 'Project Name', 'Project Description', 'Number of Files', 'Time of Scraping', 'Folder Name']
        file_headers = ['File Name', 'Is Saved', 'File URL']
        misc_headers = ['Grant Amount', 'Implementing Entity', 'Status', 'Country/Region', 'Duration', 'Approval Date', 'Transferred Amount', 'Start Date', 'Locations', 'Executing Entity', 'Sector', 'Project ID',
                        'Grant Type', 'Completion Date', 'Country']
        wb = Workbook(write_only=True)
        ws = wb.create_sheet()
        ws.title = 'Sheet1'
        ws.append(basic_headers + file_headers + misc_headers)

        for item_to_write in all_data:
            for file_to_write in item_to_write["files"]:
                row_to_write = []

                for basic_header in basic_headers:
                    row_to_write.append(item_to_write["basic"][basic_header])

                for file_header in file_headers:
                    if file_header in file_to_write:
                        row_to_write.append(file_to_write[file_header])
                    else:
                        row_to_write.append(None)

                for misc_header in misc_headers:
                    if misc_header in item_to_write["misc"]:
                        row_to_write.append(item_to_write["misc"][misc_header])
                    else:
                        row_to_write.append(None)

                ws.append(row_to_write)

        outfile_name = datetime.now().strftime("%d-%B-%Y %H_%M_%S") + " adaptation_fund_data.xlsx"
        wb.save(outfile_name)
        print("Total items scraped:", len(all_data))
        print("Created output file:", outfile_name)
        
        return


    def fetch_and_parse_data(self, input_project_url):
        data_to_return = {"basic":{"Project URL":input_project_url, "Time of Scraping":None, "Project Name":None, "Number of Files":None, "Project Description":None, "Folder Name":None},
                          "misc":{},
                          "files":[]}

        # fetch data
        fetched_data = self.db_cursor.execute("SELECT * FROM Projects WHERE project_url=? AND html IS NOT NULL", (input_project_url,)).fetchone()
        if fetched_data != None: # parse out html
            data_to_return["basic"]["Project Name"] = fetched_data[1]
            data_to_return["basic"]["Time of Scraping"] = fetched_data[3]
            data_to_return["basic"]["Number of Files"] = fetched_data[6]
            tree = html.fromstring(pickle.loads(bz2.decompress(fetched_data[2])))

            root_element = tree.xpath("./body/div[@id='wrapper']//div[contains(@id, 'post-')]")
            if len(root_element) == 1:
                # get description
                full_description_texts = []
                projectdescr_els = root_element[0].xpath("./div[contains(@class, 'project-content')]/div[contains(@class, 'project-description post-content')]/p")
                for projectdescr_el in projectdescr_els:
                    descr_part = projectdescr_el.text_content().strip()
                    if descr_part != "":
                        full_description_texts.append(descr_part)

                if len(full_description_texts) != 0:
                    data_to_return["basic"]["Project Description"] = "\n\n".join(descrpiece for descrpiece in full_description_texts)

                # get misc data
                misc_data_els = root_element[0].xpath("./div[contains(@class, 'project-content')]/div[contains(@class, 'project-info')]/div[contains(@class, 'project-info-box')]")
                for misc_data_el in misc_data_els:
                    this_misc_data_point = {"header":None, "value":None}

                    misc_header_el = misc_data_el.xpath("./h4[1]")
                    if len(misc_header_el) != 0:
                        this_misc_data_point["header"] = misc_header_el[0].text_content().strip()
                        if ":" in this_misc_data_point["header"]:
                            this_misc_data_point["header"] = this_misc_data_point["header"][0:this_misc_data_point["header"].rfind(":")].strip()

                    misc_value_el = misc_data_el.xpath("./div[contains(@class, 'project-terms')]")
                    if len(misc_value_el) != 0:
                        this_misc_data_point["value"] = misc_value_el[0].text_content().strip()

                    # add if good
                    if this_misc_data_point["header"] != None:
                        data_to_return["misc"][this_misc_data_point["header"]] = this_misc_data_point["value"]

            # create folder name for the project
            project_folder_name_object = self.create_valid_file_name(data_to_return["basic"]["Project Name"])
            project_folder_directory = None
            if project_folder_name_object["success"] == True: # create directory if it doesn't exist
                data_to_return["basic"]["Folder Name"] = project_folder_name_object["name"]
                project_folder_directory = os.path.join(self.saving_folder, project_folder_name_object["name"])
                if not os.path.exists(project_folder_directory):
                    try:
                        os.makedirs(project_folder_directory)
                    except (OSError, FileNotFoundError):
                        pass

            # go over files
            loaded_file_links = json.loads(fetched_data[5])
            seen_file_names = {} # start numerating if some already exist
            for loaded_file_link in loaded_file_links:
                this_file_item = {"File URL":loaded_file_link, "File Name":None, "Is Saved":False}

                # fetch file if possible
                fetched_file_data = self.db_cursor.execute("SELECT file_name, content, content_type FROM Files WHERE file_url=? AND content IS NOT NULL", (loaded_file_link,)).fetchone()
                if fetched_file_data != None:
                    # create a valid file name
                    file_name_object = self.create_valid_file_name(fetched_file_data[0])
                    if file_name_object["success"] == True: # figure out extension
                        guessed_extension = "." + loaded_file_link.split(".")[-1].lower()
                        if len(guessed_extension) >=7:
                            print("Unknown extension:", guessed_extension)
                            guessed_extension = mimetypes.guess_extension(fetched_file_data[2])

                        if guessed_extension != None and project_folder_directory != None: # should be good to save
                            current_file_number = 0
                            while 1:
                                if current_file_number == 0:
                                    this_file_item["File Name"] = file_name_object["name"] + guessed_extension
                                else:
                                    this_file_item["File Name"] = file_name_object["name"] + "_" + str(current_file_number) + guessed_extension

                                if this_file_item["File Name"] in seen_file_names:
                                    current_file_number+=1
                                    continue
                                else:
                                    break # good
                                
                            try:
                                with open(os.path.join(project_folder_directory, this_file_item["File Name"]), 'wb') as savefil:
                                    savefil.write(fetched_file_data[1])

                                this_file_item["Is Saved"] = True
                                seen_file_names[this_file_item["File Name"]] = ''
                            except (ValueError, TypeError, OSError, FileNotFoundError) as file_exc:
                                print("An exception while saving file for", loaded_file_link, ":", repr(file_exc))

                data_to_return["files"].append(this_file_item)


        # put a blank file if files are empty, so that something can be written
        if len(data_to_return["files"]) == 0:
            data_to_return["files"].append({})

        # check data a bit
        for key_to_check in ["Project Name"]:
            if data_to_return["basic"][key_to_check] in [None, ""]:
                print("Empty key:", key_to_check, "at", input_project_url)

        if len(data_to_return["misc"]) == 0:
            print("No misc data at", input_project_url)
        
        return data_to_return



    def create_valid_file_name(self, input_text):
        value_to_return = {"success":False, "name":None}
        forbidden_filename_characters = ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]
        
        if type(input_text) == str:
            to_return = "".join(char for char in input_text if char not in forbidden_filename_characters).strip()
            if to_return != "":
                value_to_return["name"] = to_return
                value_to_return["success"] = True
            

        return value_to_return


if __name__ == '__main__':
    parser_instance = AdaptationFund_Parser(SAVING_FOLDER, INPUT_FILE, DATABASE_NAME, BATCH_SIZE)
    parser_instance.write_data()
