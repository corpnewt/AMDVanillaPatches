#!/usr/bin/env python
import os, sys, tempfile, shutil, binascii, plistlib, subprocess, platform
from Scripts import utils, downloader, plist

class AMDPatch:
    def __init__(self):
        self.u = utils.Utils("AMDVanillaPatch")
        self.d = downloader.Downloader()
        self.urls = {
            "OC":"https://raw.githubusercontent.com/AMD-OSX/AMD_Vanilla/master/patches.plist",
            "Clover":"https://raw.githubusercontent.com/AMD-OSX/AMD_Vanilla/clover/patches.plist"
        }
        self.scripts = "Scripts"
        self.plist = None
        self.plist_data = None
        self.remove_existing = False
        # Additional non-kernel patches to remove if removing existing
        self.additional_patches = [
            {
                "Find":plist.wrap_data(binascii.unhexlify("E0117200".encode("utf-8"))),
                "Identifier":"com.apple.iokit.IOPCIFamily",
                "Name":"com.apple.iokit.IOPCIFamily",
                "Replace":plist.wrap_data(binascii.unhexlify("00000300".encode("utf-8")))
            },
            {
                "Find":plist.wrap_data(binascii.unhexlify("8400754B".encode("utf-8"))),
                "Identifier":"com.apple.iokit.IOPCIFamily",
                "Name":"com.apple.iokit.IOPCIFamily",
                "Replace":plist.wrap_data(binascii.unhexlify("0000EB00".encode("utf-8")))
            }
        ]
        self.local_cores = self._detect_cores()

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

    def _download(self, temp, url, prefix = "OC"):
        ztemp = tempfile.mkdtemp(dir=temp)
        zfile = os.path.basename(url)
        print("Downloading {}-{}...".format(prefix,os.path.basename(url)))
        self.d.stream_to_file(url, os.path.join(ztemp,zfile), False)
        script_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)),self.scripts)
        for x in os.listdir(os.path.join(temp,ztemp)):
            if "patches.plist" in x.lower():
                # Found one
                print(" - Found {}".format(x))
                print("   - Copying to {} directory...".format(self.scripts))
                if not os.path.exists(script_dir):
                    os.mkdir(script_dir)
                shutil.copy(os.path.join(ztemp,x), os.path.join(script_dir,"{}-{}".format(prefix,x)))

    def _get_config(self,pause=True):
        self.u.head("Getting Patches.plist")
        print("")
        # Download the plist
        temp = tempfile.mkdtemp()
        cwd = os.getcwd()
        for key in self.urls:
            try:
                self._download(temp,self.urls[key],prefix=key)
            except Exception as e:
                print("We ran into some problems :(\n\n{}".format(e))
        print("Cleaning up...")
        os.chdir(cwd)
        shutil.rmtree(temp)
        if pause: self.u.grab("Done.",timeout=5)
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

    def _detect_cores(self):
        try:
            _platform = platform.system().lower()
            if _platform == "darwin":
                return int(subprocess.check_output(["sysctl", "-a", "machdep.cpu.core_count"]).decode().split(":")[1].strip())
            elif _platform == "windows":
                try:
                    return int(subprocess.check_output(["wmic", "cpu", "get", "NumberOfCores"]).decode().split("\n")[1].strip())
                except:
                    data = subprocess.check_output(["powershell","-c","$p=Get-ComputerInfo -Property CsProcessors;$p.CsProcessors"]).decode().split("\n")
                    return next((int(x.split(":")[-1].strip()) for x in data if x.startswith("NumberOfCores")),-1)
            elif _platform == "linux":
                data = subprocess.check_output(["cat", "/proc/cpuinfo"]).decode().split("\n")
                for line in data:
                    if line.startswith("cpu cores"):
                        return int(line.split(":")[1].strip())
        except:
            pass
        return -1

    def _get_cpu_cores(self):
        # Let's get the number of CPU cores for the replace values
        while True:
            self.u.head("CPU Cores")
            print("")
            print("Core Count patch needs to be modified to boot your system.")
            print("")
            if self.local_cores != -1:
                print("L. Use Local Machine's Value ({:,} core{})".format(self.local_cores,"" if self.local_cores==1 else "s"))
            print("M. Return to Menu")
            print("Q. Quit")
            print("")
            cores = self.u.grab("Please enter the number of CPU cores:  ")
            if not len(cores): continue
            if cores.lower() == "m": return
            if cores.lower() == "q": self.u.custom_quit()
            if self.local_cores != -1 and cores.lower() == "l": return self.local_cores
            try:
                cores = int(cores)
                assert 0 < cores < 256
            except: continue
            return cores
    
    def _walk_patches(self,s_patch,t_patch,cpu_cores):
        changed = 0
        print("Iterating {:,} patch{}...".format(len(s_patch),"" if len(s_patch)==1 else "es"))
        for i,x in enumerate(s_patch, start=1):
            if not isinstance(x,dict):
                # Patch isn't a dict
                print(" - {}. !! Not a dictionary, skipping !!".format(i))
                continue
            found = 0
            remove = []
            print(" - {}. {}".format(str(i).rjust(3),x.get("Comment","Uncommented")))
            if "force cpuid_cores_per_package" in x.get("Comment","").lower() and "Replace" in x:
                print(" --> Needs core count patch - setting to {} core{}...".format(cpu_cores,"" if cpu_cores==1 else "s"))
                repl = binascii.hexlify(plist.extract_data(x["Replace"])).decode("utf-8")
                after = repl[:2]+hex(cpu_cores)[2:].rjust(2,"0")+repl[4:]
                x["Replace"] = plist.wrap_data(binascii.unhexlify(after.encode("utf-8")))
                find_check = ("Find","Base","MinKernel","MaxKernel","MatchOS") # Force checking of extra keys in lieu of just Find/Replace
            else:
                find_check = ("Find","Replace","Base")
            for y in t_patch:
                if not isinstance(y,dict):
                    # Skip non-dictionaries in the target
                    continue
                if all((x.get(z,"") == y.get(z,"") for z in find_check)):
                    if not found:
                        found += 1
                        print(" --> Located in target.")
                        check_pairs = [("MinKernel",""),("MaxKernel",""),("MatchKernel",""),("MatchOS",""),("MatchBuild","")]
                        if not "Replace" in find_check: # We're looking for a CPU core check
                            check_pairs.append(("Replace",x["Replace"]))
                        if not any((y in x.get("Comment","").lower() for y in ("fix pat","fix pci bus enumeration","remove non-monotonic time panic"))):
                            # We're comparing a non-PAT/PCI/non-monotonic time fix - allow those to be enabled/disabled per the user
                            check_pairs.extend([("Disabled",False),("Enabled",True)])
                        # Check Disabled, MatchOS, and MatchBuild
                        for z in check_pairs:
                            if y.get(z[0],z[1]) != x.get(z[0],z[1]):
                                changed += 1
                                if not z[0] in x:
                                    # Remove the value
                                    print(" ----> {} ({}) not found in source - removing...".format(z[0],y.get(z[0],z[1])))
                                    y.pop(z[0],None)
                                else:
                                    instances = (bytes) if sys.version_info >= (3,0) else (plistlib.Data)
                                    val1 = binascii.hexlify(plist.extract_data(y.get(z[0],z[1]))).decode("utf-8").upper() if isinstance(y.get(z[0],z[1]),instances) else y.get(z[0],z[1])
                                    val2 = binascii.hexlify(plist.extract_data(x.get(z[0],z[1]))).decode("utf-8").upper() if isinstance(x.get(z[0],z[1]),instances) else x.get(z[0],z[1])
                                    print(" ----> {} value incorrect - setting {} --> {}...".format(z[0],val1,val2))
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
        return changed

    def _patch_config(self):
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
        cpu_cores = self._get_cpu_cores()
        if not cpu_cores: return
        # Load them both and merge
        self.u.head("Patching")
        print("")
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
        if not isinstance(target_data,dict):
            # Wrong type of top-level object
            print("")
            print("Target plist's top-level object is not a dictionary.  Aborting.")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Check our plist type - prioritize OC, look for "Kernel" first, then look for "KernelAndKextPatches", then fall back to OC
        plist_type = "OC" if "Kernel" in target_data else "Clover" if "KernelAndKextPatches" in target_data else "OC"
        # Verify we have a source plist
        source = os.path.join(os.path.dirname(os.path.realpath(__file__)),self.scripts,"{}-patches.plist".format(plist_type))
        if not os.path.exists(source): self._get_config(pause=False)
        if not os.path.exists(source):
            # Still couldn't get it
            self.u.head("Error")
            print("")
            print("Unable to locate source plist.  Aborting.")
            print("")
            self.u.grab("Press [enter] to return...")
            return
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
        if not isinstance(source_data,dict):
            # Wrong type of top-level object
            print("")
            print("Source plist's top-level object is not a dictionary.  Aborting.")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        changed = 0
        # Ensure the target path exists
        if self.remove_existing:
            print("Removing ALL existing kernel patches in target plist...")
        if plist_type == "Clover": # Clover
            print("Detected Clover plist...")
            target_data = self._ensure(["KernelAndKextPatches","KernelToPatch"],target_data,list)
            source_data = self._ensure(["KernelAndKextPatches","KernelToPatch"],source_data,list)
            target_data = self._ensure(["KernelAndKextPatches","KextsToPatch"],target_data,list)
            source_data = self._ensure(["KernelAndKextPatches","KextsToPatch"],source_data,list)
            if self.remove_existing:
                target_data["KernelAndKextPatches"]["KernelToPatch"] = []
                temp_kextstopatch = []
                keys = ("Find","Replace","Name")
                for k in target_data["KernelAndKextPatches"]["KextsToPatch"]:
                    # See if it matches any additional patches
                    if any(p for p in self.additional_patches if all(k.get(key)==p.get(key,"") for key in keys)):
                        continue # Skip matches
                    temp_kextstopatch.append(k)
                # Replace the original with the modified list
                target_data["KernelAndKextPatches"]["KextsToPatch"] = temp_kextstopatch
            t_patch = target_data["KernelAndKextPatches"]["KernelToPatch"]
            s_patch = source_data["KernelAndKextPatches"]["KernelToPatch"]
            plist_type = "Clover"
        else: # Assume OpenCore
            print("Detected OpenCore plist...")
            target_data = self._ensure(["Kernel","Patch"],target_data,list)
            target_data = self._ensure(["Kernel","Quirks"],target_data,dict)
            source_data = self._ensure(["Kernel","Patch"],source_data,list)
            if self.remove_existing:
                temp_kernel_patch = []
                keys = ("Find","Replace","Identifier")
                for k in target_data["Kernel"]["Patch"]:
                    if isinstance(k,dict) and (k.get("Identifier")=="kernel" or \
                    any(p for p in self.additional_patches if all(k.get(key)==p.get(key,"") for key in keys))):
                        continue # Skip matches
                    temp_kernel_patch.append(k)
                # Replace the original with the modified list
                target_data["Kernel"]["Patch"] = temp_kernel_patch
            t_patch = target_data["Kernel"]["Patch"]
            s_patch = source_data["Kernel"]["Patch"]
            plist_type = "OC"
            if not target_data["Kernel"]["Quirks"].get("ProvideCurrentCpuInfo",False):
                changed += 1
                if not "ProvideCurrentCpuInfo" in target_data["Kernel"]["Quirks"]:
                    print("Adding missing ProvideCurrentCpuInfo...\n** Make sure OpenCore is updated to at least 0.7.1!! **")
                else:
                    print("ProvideCurrentCpuInfo disabled - enabling...")
                target_data["Kernel"]["Quirks"]["ProvideCurrentCpuInfo"] = True
        # At this point, we should be good to patch
        changed += self._walk_patches(s_patch,t_patch,cpu_cores)
        if plist_type == "Clover" and source_data["KernelAndKextPatches"].get("KextsToPatch"):
            # Check additional KextsToPatch
            print("Got KextsToPatch entries...")
            t_patch = target_data["KernelAndKextPatches"]["KextsToPatch"]
            s_patch = source_data["KernelAndKextPatches"]["KextsToPatch"]
            changed += self._walk_patches(s_patch,t_patch,cpu_cores)
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
        for key in self.urls:
            source = os.path.join(os.path.dirname(os.path.realpath(__file__)),self.scripts,"{}-patches.plist".format(key))
            print("{}: {}".format(os.path.basename(source),"Exists" if os.path.exists(source) else "Will be downloaded!"))
        print("Target plist: {}".format(self.plist))
        print("")
        print("1. Install/Update vanilla patches")
        print("2. Select target config.plist")
        print("3. Patch target config.plist")
        print("4. Remove ALL existing kernel patches in target (Currently {})".format("Enabled" if self.remove_existing else "Disabled"))
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
        elif menu == "4":
            self.remove_existing = not self.remove_existing

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
