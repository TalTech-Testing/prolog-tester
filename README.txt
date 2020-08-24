This contains the source code associated with the bachelor thesis "Development of an Automated Testing System for Swi-prolog" by Silver Schnur. SWI-Prolog version 7.2.3 and Python 3.5.2 were used to develop the tester.
Gitpython is required to use repo_tester.py, which is designed to run tests against all possible commits in a Git repository.
The current tester and tests used for that are not included, however the results produced by running the repo_tester.py are available in the CSV files.
The PlUnit fork EPlUnit is available in the tests folder and any of the tests there can be executed by running "swipl -g run_tests [test_name]"

Cool story. How about an actual readme?

Here is a link to some higher level tutorial: https://github.com/envomp/Arete-runbook/blob/master/docs/SUB_TESTER_FOR_DEVELOPER.md

Also. Don't forget to copy the eplunit.pl file to tester folder.

You can develop using docker-compose.yml file - this way you don't need anything yourself and its pretty damn fast

Also. Read comments in Dockerfile
