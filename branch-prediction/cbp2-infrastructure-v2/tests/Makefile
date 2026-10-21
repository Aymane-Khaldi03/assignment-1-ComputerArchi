CXX		=	g++
CXXFLAGS	=	-g -O2 -Wall -I../src
# toy configuration and allocation policy from the handout's hybrid predictor example
TOYFLAGS	=	-DPM_BIMODAL_BITS=4 -DPM_SET_BITS=2 -DPM_WAYS=2 -DPM_TAG_BITS=2 -DPM_ADDR_SHIFT=2 \
			-DPM_ALLOC_ON_MISPREDICT=0 -DPM_ALLOC_RESET_COUNTER=0

test:		test_example
		./test_example

test_example:	test_example.cc ../src/my_predictor.h ../src/predictor.h ../src/branch.h
		$(CXX) $(CXXFLAGS) $(TOYFLAGS) -o test_example test_example.cc

clean:
		rm -f test_example
