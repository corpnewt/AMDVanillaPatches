#!/usr/bin/env python
import os, sys, tempfile, shutil, zipfile
from Scripts import *

class AMDPatch:
    def __init__(self):
        self.u = utils.Utils("AMDVanillaPatch")
        self.d = downloader.Downloader()
        self.url = "https://raw.githubusercontent.com/AMD-OSX/AMD_Vanilla/master/patches.plist"
        self.scripts = "Scripts"
        self.plist = None
        self.plist_data = None

    def _ensure(self, path_list, dict_data, obj_type = list):
        item = dict_data
        for index,path in enumerate(path_list,1):
            if not path in item:
                if index >= len(path_list):
                    item[path] = obj_type()
                else:
                    item[path] = {}
            item = item[path]
        return dict_data

    def _download(self, temp, url):
        ztemp = tempfile.mkdtemp(dir=temp)
        zfile = os.path.basename(url)
        print("Downloading {}...".format(os.path.basename(url)))
        self.d.stream_to_file(url, os.path.join(ztemp,zfile), False)
        script_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)),self.scripts)
        for x in os.listdir(os.path.join(temp,ztemp)):
            if "patches.plist" in x.lower():
                # Found one
                print(" - Found {}".format(x))
                print("   - Copying to {} directory...".format(self.scripts))
                if not os.path.exists(script_dir):
                    os.mkdir(script_dir)
                shutil.copy(os.path.join(ztemp,x), os.path.join(script_dir,x))

    def _get_config(self):
        self.u.head("Getting Config.plist")
        print("")
        # Download the zip
        temp = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            self._download(temp,self.url)
        except Exception as e:
            print("We ran into some problems :(\n\n{}".format(e))
        print("Cleaning up...")
        os.chdir(cwd)
        shutil.rmtree(temp)
        self.u.grab("Done.",timeout=5)
        return

    def _get_plist(self):
        self.u.head("Select Plist")
        print("")
        print("Current: {}".format(self.plist))
        print("")
        print("C. Clear Selection")
        print("M. Main Menu")
        print("Q. Quit")
        print("")
        p = self.u.grab("Please drag and drop the target plist:  ")
        if p.lower() == "q":
            self.u.custom_quit()
        elif p.lower() == "m":
            return
        elif p.lower() == "c":
            self.plist = None
            self.plist_data = None
            return
        
        pc = self.u.check_path(p)
        if not pc:
            self.u.head("File Missing")
            print("")
            print("Plist file not found:\n\n{}".format(p))
            print("")
            self.u.grab("Press [enter] to return...")
            self._get_plist()
        try:
            with open(pc, "rb") as f:
                self.plist_data = plist.load(f)
        except Exception as e:
            self.u.head("Plist Malformed")
            print("")
            print("Plist file malformed:\n\n{}".format(e))
            print("")
            self.u.grab("Press [enter] to return...")
            self._get_plist()
        # Got a valid plist - let's check keys
        self.plist = pc

    def _patch_config(self):
        # Verify we have a source plist
        source = os.path.join(os.path.dirname(os.path.realpath(__file__)),self.scripts,"patches.plist")
        if not os.path.exists(source):
            self._get_config()
        if not os.path.exists(source):
            # Still couldn't get it
            self.u.head("Error")
            print("")
            print("Unable to locate source plist.  Aborting.")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Verify we have a target plist
        if not self.plist or not os.path.exists(self.plist):
            self._get_plist()
        if not self.plist or not os.path.exists(self.plist):
            # Still don't have it
            self.u.head("Error")
            print("")
            print("Unable to locate target plist.  Aborting.")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Load them both and merge
        self.u.head("Patching")
        print("")
        print("Loading source plist...")
        try:
            with open(source,"rb") as f:
                source_data = plist.load(f)
        except Exception as e:
            print("")
            print("Unable to load source plist.  Aborting.")
            print("")
            print(str(e))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        print("Loading target plist...")
        try:
            with open(self.plist,"rb") as f:
                target_data = plist.load(f)
        except Exception as e:
            print("")
            print("Unable to load target plist.  Aborting.")
            print("")
            print(str(e))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        print("Iterating patches...")
        # Ensure the target path exists
        target_data = self._ensure(["KernelAndKextPatches","KernelToPatch"],target_data,list)
        source_data = self._ensure(["KernelAndKextPatches","KernelToPatch"],source_data,list)
        t_patch = target_data["KernelAndKextPatches"]["KernelToPatch"]
        s_patch = source_data["KernelAndKextPatches"]["KernelToPatch"]
        # At this point, we should be good to patch
        changed = 0
        for x in s_patch:
            found = 0
            remove = []
            print(" - {}".format(x.get("Comment","Uncommented")))
            for y in t_patch:
                if y["Find"] == x["Find"] and y["Replace"] == x["Replace"]:
                    if not found:
                        found += 1
                        print(" --> Located in target.")
                        # Check Disabled, MatchOS, and MatchBuild
                        for z in [("Disabled",False),("MatchOS",""),("MatchBuild","")]:
                            if y.get(z[0],z[1]) != x.get(z[0],z[1]):
                                changed += 1
                                if not z[0] in x:
                                    # Remove the value
                                    print(" ----> {} ({}) not found in source - removing...".format(z[0],y.get(z[0],z[1])))
                                    y.pop(z[0],None)
                                else:
                                    print(" ----> {} value incorrect - setting {} --> {}...".format(z[0],y.get(z[0],z[1]),x.get(z[0],z[1])))
                                    y[z[0]] = x.get(z[0],z[1])
                    else:
                        print(" --> Duplicate found - removing")
                        changed += 1 
                        remove.append(y)
            if len(remove):
                for y in remove:
                    t_patch.remove(y)
            if not found:
                changed += 1
                print(" --> Not located in target, adding...")
                t_patch.append(x)
        # Now we write our target plist data
        if changed == 0:
            print("No changes made.")
        else:
            print("Writing target plist...")
            try:
                with open(self.plist,"wb") as f:
                    plist.dump(target_data,f)
            except Exception as e:
                print("")
                print("Unable to write target plist.  Aborting.")
                print("")
                print(str(e))
                print("")
                self.u.grab("Press [enter] to return...")
                return
        print("")
        print("Done.")
        print("")
        self.u.grab("Press [enter] to return...")

    def main(self):
        self.u.head()
        print("")
        source = os.path.join(os.path.dirname(os.path.realpath(__file__)),self.scripts,"patches.plist")
        print("Source plist: {}".format("Exists" if os.path.exists(source) else "Will be downloaded!"))
        print("Target plist: {}".format(self.plist))
        print("")
        print("1. Install/Update vanilla patches")
        print("2. Select target config.plist")
        print("3. Patch target config.plist")
        print("")
        print("Q. Quit")
        print("")
        menu = self.u.grab("Please select an option:  ").lower()
        if not len(menu):
            return
        if menu == "q":
            self.u.custom_quit()
        elif menu == "1":
            self._get_config()
        elif menu == "2":
            self._get_plist()
        elif menu == "3":
            self._patch_config()

a = AMDPatch()
while True:
    try:
        a.main()
    except Exception as e:
        print(e)
        if sys.version_info >= (3, 0):
            input("Press [enter] to return...")
        else:
            raw_input("Press [enter] to return...")
