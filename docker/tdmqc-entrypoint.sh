#!/bin/bash

export PYTHONPATH="${TDMQ_DIST}"


# FIXME:  how can we wait for HDFS to be ready before starting the tests?

tdmqc_run_tests

exit_code=$?

printf "======================================================================\n" >&2

if [[ $exit_code != 0 ]]; then
	printf "Tests FAILED!\n" >&2
else
	printf "Tests ran successfully!\n" >&2
fi

printf "======================================================================\n" >&2

tail -f /dev/null
