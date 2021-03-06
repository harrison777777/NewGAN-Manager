"""
NewGAN Replacement Management Tool
"""
import toga
from toga.style.pack import COLUMN, ROW
import random
from shutil import copyfileobj
import json
import re
import os
import logging
from dhooks import Webhook, Embed, File


class SourceSelection(toga.Selection):
    def __init__(self, id=None, style=None, items=None, on_select=None, enabled=True, factory=None):
        super().__init__(id=id, style=style, items=items, on_select=on_select, enabled=enabled, factory=factory)

    def add_item(self, item):
        self._items.append(item)
        self._impl.add_item(item)

    def remove_item(self, item):
        self._items.remove(item)
        items = self._items

        if self._items is []:
            pass
        else:
            self._impl.remove_all_items()
            for itm in items:
                self._impl.add_item(itm)


class NewGANManager(toga.App):
    def __init__(self, log):
        super().__init__()
        self.logger = log

    def startup(self):
        """
        Construct and show the Toga application.

        Usually, you would add your application to a main content box.
        We then create a main window (with a name matching the app), and
        show the main window.
        """
        self.logger.info("Starting Application\n------------------------------------------------")

        self.mode_info = {"Overwrite": "Overwrites already replaced faces",
                          "Preserve":  "Preserves already replaced faces",
                          "Generate": "Generates mapping from scratch."}
        os.makedirs(".config", exist_ok=True)
        self.cfg_path = ".config/cfg.json"
        self.logger.info("Loading cfg.json")
        self.config = self._load_config(self.cfg_path)
        for k, v in self.config["Profile"].items():
            if v:
                self.cur_prf = k
                break

        self.logger.info("Loading current profile")
        self.prf_cfg = self._load_config(".config/"+self.cur_prf+".json")
        self.logger.info("Creating GUI")
        self.main_box = toga.Box()
        self.logger.info("Created main box")

        # TOP Profiles
        prf_box = toga.Box()
        self.logger.info("Created prf_box")

        prf_inp = toga.TextInput()
        self.logger.info("Created prf_inp")

        self.prfsel_box = toga.Box()
        prf_lab = toga.Label(text="Create Profile: ")

        prfsel_lab = toga.Label(text="Select Profile: ")
        self.prfsel_lst = SourceSelection(items=list(self.config["Profile"].keys()), on_select=self._set_profile_status)
        self.prfsel_lst.value = self.cur_prf
        prfsel_btn = toga.Button(label="Delete", on_press=lambda e=None, c=self.prfsel_lst : self._delete_profile(c))
        prf_btn = toga.Button(label="Create", on_press=lambda e=None, d=prf_inp, c=self.prfsel_lst: self._create_profile(d, c))

        self.main_box.add(prf_box)
        prf_box.add(prf_lab)
        prf_box.add(prf_inp)
        prf_box.add(prf_btn)
        prf_lab.style.update(padding_top=7)
        prf_inp.style.update(direction=ROW, padding=(0, 20), flex=0.5)

        self.main_box.add(self.prfsel_box)
        self.prfsel_box.add(prfsel_lab)
        self.prfsel_box.add(self.prfsel_lst)
        self.prfsel_box.add(prfsel_btn)
        self.prfsel_lst.style.update(direction=ROW, padding=(0, 20), flex=0.5)
        prfsel_lab.style.update(padding_top=7)

        # MID Path selections
        dir_box = toga.Box()
        dir_lab = toga.Label(text="Select Image Directory: ")
        self.dir_inp = toga.TextInput(readonly=True, initial=self.prf_cfg['img_dir'])
        self.dir_inp.style.update(direction=ROW, padding=(0, 20), flex=0.5)

        self.dir_btn = toga.Button(label="...", on_press=self.action_select_folder_dialog, enabled=False)

        rtf_box = toga.Box()
        rtf_lab = toga.Label(text="RTF File: ")
        self.rtf_inp = toga.TextInput(readonly=True, initial=self.prf_cfg['rtf'])
        self.rtf_inp.style.update(direction=ROW, padding=(0, 20), flex=0.5)

        self.rtf_btn = toga.Button(label="...", on_press=self.action_open_file_dialog, enabled=False)

        self.main_box.add(dir_box)
        self.main_box.add(rtf_box)
        dir_box.add(dir_lab)
        dir_box.add(self.dir_inp)
        dir_box.add(self.dir_btn)
        rtf_box.add(rtf_lab)
        rtf_box.add(self.rtf_inp)
        rtf_box.add(self.rtf_btn)
        dir_lab.style.update(padding_top=7)
        rtf_lab.style.update(padding_top=7)

        gen_mode_box = toga.Box()
        self.genmde_lab = toga.Label(text="Mode: ")
        self.genmdeinfo_lab = toga.Label(text=self.mode_info["Generate"])
        self.genmde_lst = SourceSelection(items=list(self.mode_info.keys()), on_select=self.update_label)
        self.genmde_lst.value = "Generate"
        self.genmde_lst.style.update(direction=ROW, padding=(0, 20), flex=0.5)
        self.genmde_lab.style.update(padding_top=7)
        self.genmdeinfo_lab.style.update(padding_top=7)

        gen_mode_box.add(self.genmde_lab)
        gen_mode_box.add(self.genmde_lst)
        gen_mode_box.add(self.genmdeinfo_lab)
        self.main_box.add(gen_mode_box)
        # BOTTOM Generation
        gen_box = toga.Box()
        self.gen_btn = toga.Button(label="Replace Faces", on_press=self._replace_faces, enabled=False)
        self.gen_btn.style.update(padding_bottom=20)
        self.gen_lab = toga.Label(text="")

        self.gen_prg = toga.ProgressBar(max=110)
        gen_box.add(self.gen_btn)
        gen_box.add(self.gen_lab)
        gen_box.add(self.gen_prg)
        self.main_box.add(gen_box)
        self.gen_lab.style.update(padding_top=20)

        # Report bad image
        rep_box = toga.Box()
        self.rep_lab = toga.Label(text="Player UID: ")
        self.rep_inp = toga.TextInput(on_change=self.change_image)
        self.rep_img = toga.ImageView(toga.Image("resources/logo.png"))
        self.rep_img.style.update(height=180)
        self.rep_img.style.update(width=180)
        self.rep_btn = toga.Button(label="Report", on_press=self.send_report, enabled=False)

        rep_box.add(self.rep_lab)
        rep_box.add(self.rep_inp)
        rep_box.add(self.rep_img)
        rep_box.add(self.rep_btn)
        self.main_box.add(rep_box)
        self.rep_lab.style.update(padding_top=10)
        self.rep_inp.style.update(direction=ROW, padding=(0, 20), flex=0.5)


        # END configs
        rep_box.style.update(direction=ROW, padding=20)
        gen_mode_box.style.update(direction=ROW, padding=20)
        prf_box.style.update(direction=ROW, padding=20)
        self.prfsel_box.style.update(direction=ROW, padding=20)
        dir_box.style.update(direction=ROW, padding=20)
        rtf_box.style.update(direction=ROW, padding=20)
        gen_box.style.update(direction=COLUMN, padding=20, alignment='center')
        self.main_box.style.update(direction=COLUMN, padding=10, alignment='center')

        self.main_window = toga.MainWindow(title=self.formal_name, size=(1000, 600))
        self.main_window.content = self.main_box
        self.main_window.show()

    def update_label(self, widget):
        self.logger.info("Updating generation label")
        self.genmdeinfo_lab.text = self.mode_info[widget.value]

    def _load_config(self, path):
        with open(path, 'r') as fp:
            data = json.load(fp)
            return data

    def _write_config(self, path, data):
        with open(path, 'w') as fp:
            json.dump(data, fp)

    def _set_profile_status(self, e):
        self.logger.info("switch profile: {}".format(e.value))
        if e.value is None:
            self.logger.info("catch none {}".format(self.cur_prf))
        elif e.value == self.cur_prf:
            self.logger.info("catch same values")
        # if e.value == "No Profile":

        else:
            name = e.value
            self.config["Profile"][self.cur_prf] = False
            if os.path.isfile(self.prf_cfg['img_dir']+"config.xml"):
                with open('.config/'+self.cur_prf+'.xml', 'wb') as output, open(self.prf_cfg['img_dir']+'config.xml', 'rb') as input:
                    copyfileobj(input, output)

            self.config["Profile"][name] = True
            self.cur_prf = name
            self.prf_cfg = self._load_config(".config/"+self.cur_prf+".json")
            if os.path.isfile('.config/'+self.cur_prf+'.xml'):
                with open(self.prf_cfg['img_dir']+'config.xml', 'wb') as output, open('.config/'+name+'.xml', 'rb') as input:
                    copyfileobj(input, output)
            self._refresh_inp()
            if self.cur_prf == "No Profile":
                self.gen_btn.enabled = False
                self.dir_btn.enabled = False
                self.rtf_btn.enabled = False
                self.rep_btn.enabled = False
            else:
                self.gen_btn.enabled = True
                self.dir_btn.enabled = True
                self.rtf_btn.enabled = True
                self.rep_btn.enabled = True
            self._write_config(self.cfg_path, self.config)

    def _refresh_inp(self, clear=False):
        self.logger.info("Refresh Input Buttons")
        if clear:
            self.dir_inp.clear()
            self.rtf_inp.clear()
        else:
            self.dir_inp.value = self.prf_cfg['img_dir']
            self.rtf_inp.value = self.prf_cfg['rtf']

    def _create_profile(self, ent, c):
        name = ent.value
        self.logger.info("Create new profile: {}".format(name))
        self.config["Profile"][name] = False
        self._write_config(self.cfg_path, self.config)
        self._write_config(".config/"+name+".json", {"imgs": {},
                                                     "ethnics": {},
                                                     "img_dir": "",
                                                     "rtf": ""})
        ent.clear()
        open('.config/'+name+'.xml', 'a').close
        # self.cur_prf = name
        c.add_item(name)

    def _delete_profile(self, c):
        prf = c.value
        self.logger.info("Delete profile: {}".format(prf))
        if prf == "No Profile":
            self.logger.info("Can't delet no profile")
            self._throw_error("Can't delete 'No Profile'")
            return
        del self.config["Profile"][prf]
        self.config["Profile"]["No Profile"] = True
        try:
            os.remove(self.prf_cfg['img_dir']+"config.xml")
        except OSError:
            pass
        self.cur_prf = "No Profile"
        self._write_config(self.cfg_path, self.config)
        try:
            os.remove(".config/"+prf+".json")
            os.remove(".config/"+prf+".xml")
        except OSError:
            pass
        c.remove_item(prf)
        self._refresh_inp(True)
        self.gen_btn.enabled = False
        self.dir_btn.enabled = False
        self.rtf_btn.enabled = False
        self.rep_btn.enabled = False

    def parse_rtf(self, path):
        self.logger.info("Parse rtf file: {}".format(path))
        UID_regex = re.compile('([0-9]){10}')
        result_data = []
        rtf = open(path, 'r', encoding="UTF-8")
        self.logger.info(rtf)
        rtf_data = []
        for line in rtf:
            if UID_regex.search(line):
                self.logger.info(line.strip())
                rtf_data.append(line.strip())
        for newgen in rtf_data:
            data_fields = newgen.split('|')
            sec_nat = data_fields[3].strip()
            if sec_nat == '':
                sec_nat = None
            result_data.append([data_fields[1].strip(), data_fields[2].strip(), sec_nat, data_fields[7].strip()])
        return result_data

    def _throw_error(self, msg):
        self.logger.info("Error window {}:".format(msg))
        self.main_window.error_dialog('Error', msg)

    def _show_info(self, msg):
        self.logger.info("Info window: {}".format(msg))
        self.main_window.info_dialog("Info", msg)
        self.gen_lab.text = ""
        self.gen_prg.stop()
        self.gen_prg.value = 0

    def action_select_folder_dialog(self, widget):
        self.logger.info("Select Folder...")
        try:
            path_names = self.main_window.select_folder_dialog(
                title="Select image root folder"
            )
            self.dir_inp.value = path_names[0]+"/"
            self.prf_cfg['img_dir'] = path_names[0]+"/"
            self._write_config(".config/"+self.cur_prf+".json", self.prf_cfg)

        except Exception:
            pass

    def action_open_file_dialog(self, widget):
        self.logger.info("Select File...")
        try:
            fname = self.main_window.open_file_dialog(
                title="Open RTF file",
                multiselect=False,
                file_types=['rtf']
            )
            self.logger.info("Created file-dialog")
            if fname is not None:
                self.rtf_inp.value = fname
                self.prf_cfg['rtf'] = fname
                self._write_config(".config/"+self.cur_prf+".json", self.prf_cfg)
            else:
                self.prf_cfg['rtf'] = ""
                self.rtf_inp.value = ""
                self._write_config(".config/"+self.cur_prf+".json", self.prf_cfg)
        except Exception:
            self.logger.error("Fatal error in main loop", exc_info=True)
            pass

    def _replace_faces(self, widget):
        self.logger.info("Start Replace Faces")
        # get values from UI elements
        rtf = self.prf_cfg['rtf']
        img_dir = self.prf_cfg['img_dir']
        profile = self.cur_prf
        mode = self.genmde_lst.value
        self.logger.info("rtf: {}".format(rtf))
        self.logger.info("img_dir: {}".format(img_dir))
        self.logger.info("profile: {}".format(profile))
        self.logger.info("mode: {}".format(mode))
        # parse rtf
        if '' in [rtf, img_dir]:
            self._throw_error("Select RTF and/or image directory!")
            self.gen_lab.text = ""
            return
        self.gen_prg.start()
        self.gen_lab.tex = "Parsing RTF..."
        # yield 1
        rtf_data = self.parse_rtf(rtf)
        self.gen_prg.max = len(rtf_data)+10
        with open(".config/config_template", "r") as fp:
            config_template = fp.read()
        # walk all img subdirs and get all filenames. Create map
        # all_ethnicities = ["East European", "Scandinavian", "Mediterranean", "Arabian",
        #                  "African", "East Asian", "Central Asian", "Central European"]
        # all_images = []
        self.gen_lab.text = "Load profile config and create image set..."
        # yield 1
        prf_cfg = self._load_config(".config/"+profile+".json")
        if mode == "Generate":
            prf_cfg['imgs'] = {}
            prf_cfg['ethnics'] = {}
        prf_map = prf_cfg["imgs"]
        prf_eth_map = prf_cfg['ethnics']
        prf_imgs = set(prf_cfg["imgs"].values())
        xml_string = []
        self.gen_lab.text = "Restore already replaced faces if applicable..."
        # yield 1
        for k, v in prf_map.items():
            xml_string.append("<record from=\"{}\" to=\"graphics/pictures/person/{}/portrait\"/>".format(prf_eth_map[k]+"/"+v, k))

        # map rtf_data to ethnicities
        self.gen_lab.text = "Map player to ethnicity..."
        # yield 1
        for i, player in enumerate(rtf_data):
            n2_ethnic = None
            if player[2]:
                # print("DO 2nd!")
                try:
                    n2_ethnic = self.config["Ethnics"][player[2]]
                except Exception:
                    self.logger.info("Havent found 2nd Nation")
                    continue
            try:        
                n1_ethnic = self.config["Ethnics"][player[1]]
            except Exception:
                self.logger.info("Havent found 1st Nation")
                continue
            if player[3] == "1":
                if "EECA" in [n1_ethnic, n2_ethnic]:
                    p_ethnic = "EECA"
                if "Italmed" in [n1_ethnic, n2_ethnic]:
                    p_ethnic = "Italmed"
                if "SAMed" in [n1_ethnic, n2_ethnic]:
                    p_ethnic = "SAMed"
                if "South American" in [n1_ethnic, n2_ethnic]:
                    p_ethnic = "South American"
                if "SpanMed" in [n1_ethnic, n2_ethnic]:
                    p_ethnic = "SpanMed"
                if "YugoGreek" in [n1_ethnic, n2_ethnic]:
                    p_ethnic = "YugoGreek"
            elif player[3] in ["3", "6", "7", "8", "9"]:
                p_ethnic = "African"
            elif player[3] == "10":
                p_ethnic = "Asian"
            elif player[3] == "2":
                p_ethnic = "MENA"
                if "MESA" in [n1_ethnic, n2_ethnic]:
                    p_ethnic = "MESA"
            elif player[3] == "5":
                p_ethnic = "Seasian"
            elif player[3] == "0":
                p_ethnic = "Central European"
                if "Scandinavian" in [n1_ethnic, n2_ethnic]:
                    p_ethnic = "Scandinavian"
                elif "Caucasian" in [n1_ethnic, n2_ethnic]:
                    p_ethnic = "Caucasian"
            elif player[3] == "4":
                p_ethnic = "MESA"
            if player[0] in prf_map:
                if mode == "Preserve":
                    self.logger.info("Preserve: {} {}".format(i, p_ethnic))
                    self.gen_prg.value += 1
                    # yield 0.001
                    continue
                elif mode == "Overwrite":
                    self.logger.info("Overwrite: {} {}".format(i, p_ethnic))
                    player_img = prf_map[player[0]]
                    prf_imgs.remove(player_img)
            eth_imgs = set([f.name for f in os.scandir(self.prf_cfg['img_dir']+p_ethnic) if f.is_file()])
            selection_pool = eth_imgs - prf_imgs
            # print("eth_imgs:", eth_imgs)
            # print("prf_imgs:", prf_imgs)
            # print("sel pool:", selection_pool)
            player_img = random.choice(tuple(selection_pool))
            prf_map[player[0]] = player_img
            prf_eth_map[player[0]] = p_ethnic
            prf_imgs.add(player_img)
            player_img = player_img.split('.')[0]

        # create config file entry
            xml_string.append("<record from=\"{}\" to=\"graphics/pictures/person/{}/portrait\"/>".format(p_ethnic+"/"+player_img, player[0]))
            self.gen_prg.value += 1
            # yield 0.001
            self.logger.info("{} {}".format(i, p_ethnic))

        # save profile metadata (used pics and config.xml)
        self.gen_lab.text = "Generate config.xml..."
        # yield 1
        xml_players = "\n".join(xml_string)
        xml_config = config_template.replace("[players]", xml_players)
        with open(self.prf_cfg['img_dir']+"config.xml", 'w') as fp:
            fp.write(xml_config)
        self.gen_lab.text = "Save metadata for profile..."
        # yield 1
        prf_cfg["imgs"] = prf_map
        self._write_config(".config/"+profile+".json", prf_cfg)
        self.gen_prg.value += 10
        # yield 0
        self.gen_lab.text = "Finished! :)"
        self._show_info("Finished! :)")

    def change_image(self, id):
        self.logger.info("try to change image preview")
        uid = id.value
        try:
            img_name = self.prf_cfg["imgs"][uid]
            img_eth = self.prf_cfg["ethnics"][uid]
            img_path = self.prf_cfg["img_dir"] + "/" + img_eth + "/" + img_name
            self.rep_img.image = toga.Image(img_path)
            self.logger.info("change image preview to: {}".format(img_path))
        except Exception:
            self.logger.info("changing image preview failed!")
            return

    def send_report(self, e):
        uid = self.rep_inp.value
        img_name = self.prf_cfg["imgs"][uid]
        img_eth = self.prf_cfg["ethnics"][uid]
        img_path = img_eth + "/" + img_name
        img_file = self.rep_img.image.path
        self.logger.info("send report: {}".format(img_file))

        hook = Webhook("https://discord.com/api/webhooks/770397581149863946/Wls0g6LEyTXEpOqzfLn2YuDRKANFSAFpwKe62VL9IxpwsQDWFjYHVfy19hrYiv5p0X2a")

        embed = Embed(
            description='A user reported the following face',
            color=0x5CDBF0,
            timestamp='now'  # sets the timestamp to current time
            )

        file = File(img_file)
        embed.add_field(name='File', value=img_path)

        hook.send(embed=embed, file=file)


def main():
    # create logger with 'spam_application'
    logger = logging.getLogger('NewGAN Logger')
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler('newgan.log')
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    try:
        return NewGANManager(logger)
    except Exception:
        logger.error("Fatal error in main loop", exc_info=True)
