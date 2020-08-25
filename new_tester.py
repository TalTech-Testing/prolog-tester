import csv
import json
import os
import subprocess
import sys
import time
from collections import OrderedDict
from io import StringIO
from re import match
import re
from shutil import rmtree, copy2, copystat, Error


def sh(cmd):
    """
    Executes the command.
    Returns (returncode, stdout, stderr, Popen object)
    """
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out, err = p.communicate()
    out = out.decode("utf-8")
    err = err.decode("utf-8")
    return p.returncode, out, err, p


output_format = """  {unit}-{name}: {description} (weight: {weight})
    {result}
"""


def copyfiles(src, dst, ignore=None):
    """
    https://docs.python.org/2/library/shutil.html#copytree-example
    with some modifications (destination folder can exist)
    """
    names = os.listdir(src)
    files = []
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    if not os.path.exists(dst):
        os.makedirs(dst)
    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if os.path.isdir(srcname):
                files += copyfiles(srcname, dstname, ignore)
            else:
                copy2(srcname, dstname)
                files += [dstname]
            # XXX What about devices, sockets etc.?
        except (IOError, os.error) as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error as err:
            errors.extend(err.args[0])
    try:
        copystat(src, dst)
    except WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError as why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise Error(errors)
    return files


testing_path = "/tmp/prolog-tester"
main_test_re = "test_pr.*\.pl"
line_re = r".pl:(\d+)"
csv_separator = "START_SIMPLE_REPORT\n"


def main_tests(files):
    for file_name in files:
        file_name = os.path.relpath(file_name, testing_path)
        if match(main_test_re, file_name):
            yield file_name


def test(json_string):
    try:
        rmtree(testing_path)
    except FileNotFoundError:
        pass
    input_data = json.loads(json_string)

    output = {"type": "arete"}

    source = []
    for path, _, files in os.walk(input_data["contentRoot"]):
        for file_name in files:
            source_file = {}
            file_path = os.path.join(path, file_name)
            source_file["path"] = file_path
            with open(file_path, encoding='utf-8') as f:
                source_file["contents"] = f.read()
            source.append(source_file)
    output["files"] = source

    content_files = copyfiles(input_data["contentRoot"], testing_path)
    test_files = copyfiles(input_data["testRoot"], testing_path)

    overwritten_files = []
    for file_name in content_files:
        if file_name in test_files:
            overwritten_files.append(os.path.relpath(file_name, testing_path))

    total_points = 0
    total_granted = 0
    output["errors"] = []

    if overwritten_files:
        for file in overwritten_files:
            error = dict()
            error["lineNo"] = 0
            error["columnNo"] = 0
            error["fileName"] = file
            error["hint"] = "Please rename the following file: {}".format(file)
            output["errors"].append(error)
        output["style"] = 0
        output["totalGrade"] = 0
        return json.dumps(output)

    test_suites = []
    console_output = []

    for grade_code, test_file in enumerate(main_tests(test_files), start=1):
        test_context = dict()
        test_context["startDate"] = time.time()
        test_context["file"] = test_file
        test_context["name"] = test_file.replace(".pl", "")
        test_context["unitTests"] = []
        points = 0
        granted = 0

        passed_tests = 0
        total_tests = 0

        test_output = ""
        _, out, err, _ = sh("cd {} && swipl -qg run_tests -t halt {}".format(testing_path, test_file))
        result = {"stdout": out, "stderr": err, "grade_type_code": grade_code, "name": test_file}
        test_context["endDate"] = time.time()
        console_output.append("file: {} stdout:\n{}".format(test_file, out))
        console_output.append("file: {} stderr:\n{}".format(test_file, err))
        if err:
            for line in err.split("\n"):
                error = dict()
                error["lineNo"] = 0
                error["columnNo"] = 0
                error["fileName"] = test_file
                error["message"] = line
                if line.startswith("ERROR"):
                    error["hint"] = "Make sure your code works locally first"
                output["style"] = 0
                matches = re.findall(line_re, line)
                if len(matches) > 0:
                    error["lineNo"] = matches[0]
                output["errors"].append(error)

        csv_start = out.rfind(csv_separator)
        if csv_start < 0:
            error = dict()
            error["lineNo"] = 0
            error["columnNo"] = 0
            error["fileName"] = test_file
            error["message"] = "{} was not found in the tester output.\n".format(repr(csv_separator))
            error["hint"] = "This shouldn't happen..."
            output["style"] = 0
            output["errors"].append(error)
        else:
            csv_start += len(csv_separator)

            result_reader = csv.reader(StringIO(out[csv_start:]))
            test_results = OrderedDict()

            for row in result_reader:
                test_result = row[0]
                if test_result == 'Fixme':
                    if row[-1] == 'passed':
                        test_result = 'Passed'
                    else:
                        test_result = 'Failed'
                    row = row[:-1]
                list = test_results.get(test_result, [])
                list.append(row[1:])
                test_results[test_result] = list

            for category, tests in test_results.items():
                for test in tests:
                    unit_test = dict()
                    try:
                        unit_test["timeElapsed"] = float(test[-1]) * 1000
                    except ValueError:
                        unit_test["timeElapsed"] = -1
                    unit_test["weight"] = int(test[3])
                    test_weight = int(test[3])
                    points += test_weight
                    total_tests += 1
                    unit_test["name"] = "{}-{}".format(test[0], test[1])
                    unit_test["printExceptionMessage"] = "false"
                    unit_test["printStackTrace"] = "false"

                    def fill_fields(test, unit_test):
                        if test[0] == "description":
                            unit_test["exceptionClass"] = test[1]
                            unit_test["exceptionMessage"] = test[2]
                        else:
                            unit_test["exceptionClass"] = test[0]

                    if category == 'Passed':
                        granted += test_weight
                        passed_tests += 1
                        unit_test["status"] = "PASSED"
                    elif category == 'Failed':
                        unit_test["status"] = "FAILED"
                        fill_fields(test, unit_test)
                    else:
                        unit_test["status"] = "SKIPPED"
                        fill_fields(test, unit_test)
                    test_context["unitTests"].append(unit_test)

        if points == 0:
            error = dict()
            error["lineNo"] = 0
            error["columnNo"] = 0
            error["fileName"] = "root"
            error["hint"] = "No tests were run."
            output["errors"].append(error)
            output["style"] = 0
            test_context["grade"] = 0
        else:
            test_context["grade"] = 100.0 * granted / points
        test_context["passedCount"] = passed_tests
        result["output"] = test_output
        total_points += points
        total_granted += granted
        test_suites.append(test_context)

    output["consoleOutput"] = console_output
    output["testSuites"] = test_suites
    if total_points == 0:
        output["percentage"] = 0
    else:
        output["percentage"] = 100.0 * total_granted / total_points
    return json.dumps(output)


if __name__ == '__main__':
    json_string = "".join(sys.stdin)
    print(test(json_string))
