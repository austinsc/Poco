from __future__ import print_function
import os
import time
import string
import shutil
import sys
import argparse
import subprocess
import itertools
#import multiprocessing

__author__ = "Stephen C. Austin"

tmain1 = time.clock()


# Utility Functions
def benchmark(func):
	def wrapper(*arg):
		t1 = time.clock()
		res = func(*arg)
		t2 = time.clock()
		if(t2 - t1 < 1.0):
			print("/////////////// %s took %0.3f ms" % (func.func_name, (t2 - t1) * 1000.0))
		else:
			print("/////////////// %s took %0.3f sec" % (func.func_name, t2 - t1))
		
		return res
	return wrapper
	
def validate_pair(ob):
    try:
        if not (len(ob) == 2):
            print("Unexpected result:", ob, file=sys.stderr)
            raise ValueError
    except:
        return False
    return True

def consume(iter):
    try:
        while True: next(iter)
    except StopIteration:
        pass

def findVCEnvironment(version, arch="x86", initial=None):
    from distutils.msvc9compiler import find_vcvarsall
    # find the selected environment batch file
    vcvarsall = find_vcvarsall(version)
    # set up the command
    env_cmd = [vcvarsall, arch]
    # construct the command that will alter the environment
    env_cmd = subprocess.list2cmdline(env_cmd)
    # create a tag so we can tell in the output when the proc is done
    tag = 'Done running command'
    # construct a cmd.exe command to do accomplish this
    cmd = 'cmd.exe /s /c "{env_cmd} && echo "{tag}" && set"'.format(**vars())
    # launch the process
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=initial)
    # parse the output sent to stdout
    lines = proc.stdout
    # consume whatever output occurs until the tag is reached
    consume(itertools.takewhile(lambda l: tag not in l, lines))
    # define a way to handle each KEY=VALUE line
    handle_line = lambda l: l.rstrip().split('=',1)
    # parse key/values into pairs
    pairs = map(handle_line, lines)
    # make sure the pairs are valid
    valid_pairs = filter(validate_pair, pairs)
    # construct a dictionary of the pairs
    result = dict(valid_pairs)
    # let the process finish
    proc.communicate()
    return result

def findAvailableGenerators(mode="cmake"):
    cmd = mode + " --help"
    pr = subprocess.Popen(cmd, cwd=os.path.abspath(os.getcwd()), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, error) = pr.communicate()
    
    generators = []
    try:
        lines = str(out).split("\nGenerators")[1]        
        for line in lines.split("\n"):
            if("=" in line):
                gen = line.split("=")[0].strip().replace("\n", "")
                if gen != "":
                    generators += [gen]
    except:
        print(error)
        sys.exit(pr.returncode)        
    return generators
    
def findGitRevisionNumber():
    gitcmd = "git rev-parse --short HEAD"
    pr = subprocess.Popen(gitcmd, cwd=os.path.abspath(os.getcwd()), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, error) = pr.communicate()
    try:
        result = str(out).replace("\n", "")
        if(result == ''):
            result = '0'
        return result
    except:
        print(error)
        return '0'

def findGitRevision():
    gitcmd = "git rev-parse HEAD"
    pr = subprocess.Popen(gitcmd, cwd=os.path.abspath(os.getcwd()), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, error) = pr.communicate()
    try:
        result = str(out).replace("\n", "")
        if(result == ''):
            result = '0'
        return result
    except:
        print(error)
        return '0'
    
def findProjects():
    results = ["All"]
    dirname = os.getcwd()
    for f in os.listdir(dirname):
        if os.path.isdir(os.path.join(dirname, f)):
            if os.path.exists(os.path.join(dirname, f, "CMakeLists.txt")):
                results += [f]
    return results
                
def findDevelopmentRoot():
    # Try to find the default development root    
    if(os.environ.get("DEVROOT", "") == "" and os.path.exists(os.path.join(os.getcwd(), "../../../"))):
        os.environ["DEVROOT"] = os.path.join(os.getcwd(), "../../../")
    return os.environ["DEVROOT"]
    
def findTools():
	if(sys.platform == "win32"):
		return ["msvc","mingw","make","nmake","jom"]

	elif(sys.platform == "darwin"):
		return ["xcode","make"]

	elif("linux" in sys.platform):
		return ["make"]
    
def findGenerator(tool, toolVersion, architecture, generator=None):
    if(generator == None or generator not in findAvailableGenerators()):
        if(tool == "xcode"):
            generator = "Xcode"
        elif(tool == "make"):
            generator = "'Unix Makefiles'"
        elif(tool == "mingw"):
            generator = "MinGW Makefiles"
        elif(tool == "msvc"):
            if(toolVersion == 9):
                generator = "Visual Studio 9 2008"
            elif(toolVersion in [10, None]):
                generator = "Visual Studio 10"
            elif(toolVersion == 11):
                generator = "Visual Studio 11"
            # Append Win64 to the generator name for x64
            if(architecture == "x64"):
                generator += " Win64"
        elif(tool == "nmake"):
            generator = "NMake Makefiles"
        elif(tool == "jom"):
            generator = "NMake Makefiles JOM"
    return generator

def findInstaller(installer=None):
    if(installer == None or installer not in findAvailableGenerators("cpack")):
        if(sys.platform == "win32"):
            return "NSIS"

        elif(sys.platform == "darwin"):
            return "PackageMaker"

        elif("linux" in sys.platform):
            return "STGZ"
    return installer
    
def findEnvironment(tool, toolVersion, architecture):
    if(tool in ["msvc", "nmake", "jom"]):
        if(architecture == "x64"):
            return findVCEnvironment(float(toolVersion), "amd64")
        else:
            return findVCEnvironment(float(toolVersion), architecture)
    else:
        return None

def restoreEnvironment(sourceDirectory):
    os.chdir(sourceDirectory)
       
def runCMake(cmakeArgs, args):
    print(" ".join(cmakeArgs))
    if sys.platform == "win32":
        proc = subprocess.Popen(subprocess.list2cmdline(cmakeArgs), env=args.environment)
    else:
        proc = subprocess.Popen(" ".join(cmakeArgs), shell=True, env=args.environment)
    proc.communicate()
    return proc.returncode

@benchmark
def updateStep(args):
    cwd = os.getcwd()
    os.chdir(args.sourceDirectory)
    
    # Make sure that the root directory is up to date
    print("Updating " + args.sourceDirectory + "...", end="")
    subprocess.Popen("git pull", cwd=os.path.abspath(args.sourceDirectory), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    subprocess.Popen("git submodule init", cwd=os.path.abspath(args.sourceDirectory), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    subprocess.Popen("git submodule update", cwd=os.path.abspath(args.sourceDirectory), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    print("Success!")
    
    # Find all of the submodules in the source directory
    submodules = []
    dirname = args.sourceDirectory
    for f in os.listdir(dirname):
        if os.path.isdir(os.path.join(dirname, f)):
            if os.path.exists(os.path.join(dirname, f, ".git")):
                submodules += [f]
    
    # Loop through the submodules and make sure they are on the master branch and the latest revision
    for sm in submodules:
        print("Updating " + sm + "...", end="")
        os.chdir(sm)
        subprocess.Popen("git checkout master", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        subprocess.Popen("git pull", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        os.chdir(args.sourceDirectory)
        print("Success!")
        
    # Reset the working directory back to whatever it was
    os.chdir(cwd)
    
@benchmark
def cleanStep(args):
    if(not args.stageDirectory == args.sourceDirectory):
        if(os.path.exists(args.stageDirectory)):
            print("Cleaning... ", end="")
            for f in os.listdir(args.stageDirectory):
                try:
                    os.unlink(os.path.join(folder, f))
                except Exception, e:
                    pass
            if len(os.listdir(args.stageDirectory)) > 0:
                print("Failed!")
                print("The bootstrapper was unable to clean completely. Some files may be locked by another process.")
            else:
                print("Success!") 

@benchmark
def purgeStep(args):
    print("Purging... ", end="")
    try:
        cacheFile = os.path.join(args.stageDirectory, "CMakeCache.txt")
        cacheDir = os.path.join(args.stageDirectory, "CMakeFiles")
        if(os.path.exists(cacheFile)):
            os.remove(cacheFile)
        if(os.path.exists(cacheDir)):
            shutil.rmtree(cacheDir)
        print("Success!")
    except:
        print("Failed!")
        print("The bootstrapper was unable to purge completely. Some files may be locked by another process.")
    
@benchmark
def configureStep(args):
    args.generator = findGenerator(args.tool, args.toolVersion, args.architecture, args.generator)
    args.environment = findEnvironment(args.tool, args.toolVersion, args.architecture)
    cmakeArgs = ["cmake"
                ,"-G", "{0}".format(args.generator)
                ,"-DBOOTSTRAP_DEVROOT_DIR:PATH={dev_root}".format(dev_root=args.developmentRoot)
                ,"-DBOOTSTRAP_ARCHITECTURE:STRING={arch}".format(arch=args.architecture)
                ,"-DBOOTSTRAP_PROJECT:STRING={p}".format(p=args.project)
                ,"-DBOOTSTRAP_NO_TESTS:BOOLEAN={o}".format(o=args.notests)
                ,"-DBOOTSTRAP_NO_BINDINGS:BOOLEAN={o}".format(o=args.nobindings)
                ,"-DBOOTSTRAP_NO_INSTALLER:BOOLEAN={o}".format(o=args.noinstaller)
                ,"-DBOOTSTRAP_CONFIGURATION:STRING={c}".format(c=args.configuration)
                ,"-DBOOTSTRAP_VERSION_MAJOR:STRING={v}".format(v=args.versionMajor)
                ,"-DBOOTSTRAP_VERSION_MINOR:STRING={v}".format(v=args.versionMinor)
                ,"-DBOOTSTRAP_VERSION_BUILD:STRING={v}".format(v=args.versionBuild)
                ,"-DBOOTSTRAP_VERSION_REVISION:STRING={v}".format(v=args.versionRevision)
                ,"-DBOOTSTRAP_VERSION_SOURCE:STRING={v}".format(v=args.versionSource)                
                ,"-DBOOTSTRAP_PROJECT_INCLUDE_DIR_NAME:STRING={v}".format(v=args.projectIncludeDirectory)
                ,"-DBOOTSTRAP_PROJECT_SOURCE_DIR_NAME:STRING={v}".format(v=args.projectSourceDirectory)
                ,"-DBOOTSTRAP_PROJECT_RESOURCE_DIR_NAME:STRING={v}".format(v=args.projectResourceDirectory)
                ,"-DBOOTSTRAP_PROJECT_TEST_DIR_NAME:STRING={v}".format(v=args.projectTestDirectory)
                ,"-DBOOTSTRAP_PROJECT_TEST_SUFFIX:STRING={v}".format(v=args.projectTestSuffix)
                ,"-DBOOTSTRAP_PROJECT_GUI_DIR_NAME:STRING={v}".format(v=args.projectGUIDirectory)
                ,"-DBOOTSTRAP_PROJECT_BINDING_DIR_NAME:STRING={v}".format(v=args.projectBindingDirectory)
                ,"-DBOOTSTRAP_PROJECT_BINDING_SUFFIX:STRING={v}".format(v=args.projectBindingSuffix)
                ,"-DBOOTSTRAP_PROJECT_SPEC_DIR_NAME:STRING={v}".format(v=args.projectSpecDirectory)
                ,"{relative_path_to_source}".format(relative_path_to_source=args.sourceDirectoryRel)]    
    ec = runCMake(cmakeArgs, args)
    if(not ec == 0):
        print("An error occured while the bootstrapper was performing the 'configure' step. Check the output for more details.")
        sys.exit(ec)

@benchmark
def buildStep(args):
    cmakeArgs = ["cmake", "--build", ".", "--config", args.configuration]
    if(args.rebuild):
        cmakeArgs += ["--clean-first"]
    ec = runCMake(cmakeArgs, args)
    if(not ec == 0):
        print("An error occured while the bootstrapper was performing the 'build' step. Check the output for more details.")
        sys.exit(ec)

@benchmark
def testStep(args):
    ec = runCMake(["ctest", "--output-on-failure", "-C", args.configuration], args)
    if(not ec == 0):
        print("An error occured during the test step. Check the output for more details.")
        sys.exit(ec)

@benchmark
def installStep(args):
    args.installer = findInstaller(args.installer)
    ec = runCMake(["cpack", "-G", args.installer], args) #, "-C", args.configuration
    if(not ec == 0):
        print("An error occured while the bootstrapper was performing the install step. Check the output for more details.")
        sys.exit(ec) 
    
        
def printHeader():
    print("    Universal CMake Project Bootstrapper")
    print("    (c)2012 Pwnt & Co. All rights reserved.")

    
# Main
## Print the header
printHeader()

## Construct the argument parser
parser = argparse.ArgumentParser(prog="python bootstrap.py", description="Configure, build, and test the Pwnt & Co. project.", version=0.4,
                                 formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, max_help_position=50, width=160),
                                 epilog="For more information on how to use this tool, please consult the readme file.")
subparsers = parser.add_subparsers(title="Bootstrap Commands", description="Different command mode options to alter what actions are performed.", 
                                   help="For more information on the different commands available, please consult the readme file.", dest="mode")


## Update Command
updateParser = subparsers.add_parser("update", help="This command updates the source code and submodules from the repository.")
updateParser.set_defaults(func=updateStep)
                                   
## Clean Command
cleanParser = subparsers.add_parser("clean", help="The clean command completely removes the build system's temporary working directory, including all generated project files and CMake caches.")
cleanParser.set_defaults(func=cleanStep)

## Purge Command
purgeParser = subparsers.add_parser("purge", help="Purge only removes CMake caches in the temporary working directory which causes them to be recreated next time the configure command is used.")
purgeParser.set_defaults(func=purgeStep)

## Configure Command
configureParser = subparsers.add_parser("configure", help="The configure command executes CMake with the specified parameters to produce project files in the given temporary working directory. Configure must be used prior to building, testing, or installing with the bootstrapper.")
projGroup = configureParser.add_argument_group("Project Parameters")
projGroup.add_argument(dest="project", metavar="project", nargs="?", type=str, default="All", help="Project selection")
projGroup.add_argument("-a", dest="architecture", type=str, default="x64", choices=["x86", "x64"], help="Target architecture")
projGroup.add_argument("-c", dest="configuration", type=str, default="Debug", choices=["Debug", "Release"], help="Target output configuration")
projGroup.add_argument("--no-tests", dest="notests", default=False, const=True, action='store_const', help="Configure the projects without tests")
projGroup.add_argument("--no-bindings", dest="nobindings", default=False, const=True, action='store_const', help="Configure the projects without python bindings")
projGroup.add_argument("--no-installer", dest="noinstaller", default=False, const=True, action='store_const', help="Configure the projects without an installer")

structureGroup = configureParser.add_argument_group("Project Directory Structure")
structureGroup.add_argument("-inc", metavar="incdir", dest="projectIncludeDirectory", type=str, default="inc", help="Project include directory name")
structureGroup.add_argument("-src", metavar="srcdir", dest="projectSourceDirectory", type=str, default="src", help="Project source directory name")
structureGroup.add_argument("-res", metavar="resdir", dest="projectResourceDirectory", type=str, default="res", help="Project resource directory name")
structureGroup.add_argument("-test", metavar="testdir", dest="projectTestDirectory", type=str, default="test", help="Project test directory name")
structureGroup.add_argument("-test-suffix", metavar="suffix", dest="projectTestSuffix", type=str, default="Test", help="Project test source file suffix")
structureGroup.add_argument("-gui", metavar="guidir", dest="projectGUIDirectory", type=str, default="gui", help="Project Qt UI directory name")
structureGroup.add_argument("-bind", metavar="pydir", dest="projectBindingDirectory", type=str, default="py", help="Project language bindings directory name")
structureGroup.add_argument("-bind-suffix", metavar="pydir", dest="projectBindingSuffix", type=str, default="Wrapper", help="Project language bindings source file suffix")
structureGroup.add_argument("-spec", metavar="specdir", dest="projectSpecDirectory", type=str, default="spec", help="Project object specification directory name")

versionGroup = configureParser.add_argument_group("Version Parameters")
versionGroup.add_argument("-vm", dest="versionMajor", metavar="major", type=int, default=0, help="Major version number")
versionGroup.add_argument("-vi", dest="versionMinor", metavar="minor", type=int, default=0, help="Minor version number")
versionGroup.add_argument("-vb", dest="versionBuild", metavar="build", type=int, default=0, help="Build number")
versionGroup.add_argument("-vr", dest="versionRevision", metavar="revision", type=str, default=findGitRevisionNumber(), help="Revision string")
versionGroup.add_argument("-vs", dest="versionSource", metavar="source", type=str, default=findGitRevision(), help="Source control identifier")

toolGroup = configureParser.add_argument_group("Tool Parameters")
toolGroup.add_argument("-t", dest="tool", type=str, default=findTools()[0], choices=findTools(), help="Compiler/linker/IDE tool chain")
toolGroup.add_argument("-tv", dest="toolVersion", type=int, default=10 if (sys.platform == "win32") else 0, choices=[9, 10, 11, 0] if (sys.platform == "win32") else [0], help="Compiler/linker/IDE tool chain version (Windows Only)")
toolGroup.add_argument("-d", dest="developmentRoot", metavar="/path/to/devroot", type=str, default=findDevelopmentRoot(), help="Development root directory hint")
toolGroup.add_argument("-g", dest="generator", metavar="'CMake Generator'", type=str, default=None, help="CMake generator override")
toolGroup.set_defaults(func=configureStep)

## Build Command
buildParser = subparsers.add_parser("build", help="Build executes the configured projects with the registered compiler/linker tool chain.")
buildGroup = buildParser.add_argument_group("Build Parameters")
buildGroup.add_argument("-c", dest="configuration", type=str, default="Debug", choices=["Debug", "Release"], help="Target output configuration")
buildGroup.add_argument("-r", dest="rebuild", default=False, const=True, action='store_const', help="Remove compiler/linker output prior to building")
buildParser.set_defaults(func=buildStep)

## Test Command
testParser = subparsers.add_parser("test", help="Once the project has been successfully built, test will run the compiled tests (if there are any), and save the test results to the output directory.")
testParser.add_argument("-c", dest="configuration", type=str, default="Debug", choices=["Debug", "Release"], help="Target output configuration")
testParser.set_defaults(func=testStep)

## Install Command
installParser = subparsers.add_parser("install", help="The install command will produce a platform specific installer based on the installation generator specified. This command requires a successful build command in order to operate.")
installGroup = installParser.add_argument_group("Installation Parameters")
installGroup.add_argument("-i", dest="installer", type=str, default=None, choices=findAvailableGenerators("cpack"), help="Installation generator")
installParser.set_defaults(func=installStep)

eGroup = parser.add_argument_group("Standard Environment Parameters")
eGroup.add_argument("-s", dest="sourceDirectory", metavar="/path/to/source", type=str, default=os.getcwd(), help="Project source code root directory")
eGroup.add_argument("-w", dest="stageDirectory", metavar="/path/to/build/dir", type=str, default="./stage", help="Compiler/linker/IDE output directory")

## Prepare the args
args = parser.parse_args()
args.environment = None
args.sourceDirectory = os.path.abspath(args.sourceDirectory)
args.stageDirectory = os.path.abspath(args.stageDirectory)
args.sourceDirectoryRel = os.path.relpath(args.sourceDirectory, args.stageDirectory)
if(not args.stageDirectory == args.sourceDirectory):
    if(not os.path.exists(args.stageDirectory)):
        os.makedirs(args.stageDirectory)
os.chdir(args.stageDirectory)    

## Execute the selected command
args.func(args)
    
## Clean up
os.chdir(args.stageDirectory)

## Print the bootstrapper execution time
tmain2 = time.clock()
if(tmain2 - tmain1 < 1.0):
    print("/////////////// Bootstrap Total: %0.3f ms" % ((tmain2 - tmain1) * 1000.0))
else:
    print("/////////////// Bootstrap Total: %0.3f sec" % (tmain2 - tmain1))
