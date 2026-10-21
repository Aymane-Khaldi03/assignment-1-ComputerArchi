// my_predictor.h
// This file contains a sample gshare_predictor class.
// It is a simple 32,768-entry gshare with a history length of 15.

class gshare_update : public branch_update {
public:
	unsigned int index;
};

class gshare_predictor : public branch_predictor {
public:
#define HISTORY_LENGTH	15
#define TABLE_BITS	15
	gshare_update u;
	branch_info bi;
	unsigned int history;
	unsigned char tab[1<<TABLE_BITS];

	gshare_predictor (void) : history(0) { 
		memset (tab, 0, sizeof (tab));
	}

	branch_update *predict (branch_info & b) {
		bi = b;
		if (b.br_flags & BR_CONDITIONAL) {
			u.index = 
				  (history << (TABLE_BITS - HISTORY_LENGTH)) 
				^ (b.address & ((1<<TABLE_BITS)-1));
			u.direction_prediction (tab[u.index] >> 1);
		} else {
			u.direction_prediction (true);
		}
		u.target_prediction (0);
		return &u;
	}

	void update (branch_update *u, bool taken, unsigned int target) {
		if (bi.br_flags & BR_CONDITIONAL) {
			unsigned char *c = &tab[((gshare_update*)u)->index];
			if (taken) {
				if (*c < 3) (*c)++;
			} else {
				if (*c > 0) (*c)--;
			}
			history <<= 1;
			history |= taken;
			history &= (1<<HISTORY_LENGTH)-1;
		}
	}
};

//
// Pentium M hybrid branch predictors
// This class implements a simple hybrid branch predictor based on the Pentium M branch outcome prediction units. 
// Instead of implementing the complete Pentium M branch outcome predictors, the class below implements a hybrid 
// predictor that combines a bimodal predictor and a global predictor.
//
// Bimodal table: 2^PM_BIMODAL_BITS 2-bit counters indexed by branch address.
// Global predictor: set-associative "cache" of 2-bit counters with
// 2^PM_SET_BITS sets, PM_WAYS ways and PM_TAG_BITS-bit tags, LRU replacement.
// It is accessed with h = (address ^ GHR), GHR being PM_SET_BITS+PM_TAG_BITS
// bits long; the upper PM_SET_BITS bits of h select the set and the lower
// PM_TAG_BITS bits are the tag (same split as the hybrid example in the
// assignment handout). On a tag hit the global prediction is used, otherwise
// the bimodal prediction is used. By default a global entry is allocated only
// when the bimodal table mispredicts (PM_ALLOC_ON_MISPREDICT); the handout's
// example allocates on every miss, which tests/test_example.cc reproduces.
// The loop predictor, the PIR hash and the target predictor are not modeled.
//
// Defaults follow the Pentium M sizes from Uzelac & Milenkovic (ISPASS'09):
// 4K-entry bimodal table, 2K-entry 4-way global predictor (512 sets).
// Every parameter can be overridden with -D at compile time.
#ifndef PM_GLOBAL
#define PM_GLOBAL		1	// 0: disable the global predictor (bimodal-only baseline)
#endif
#ifndef PM_BIMODAL_BITS
#define PM_BIMODAL_BITS		12	// 4096 bimodal counters
#endif
#ifndef PM_SET_BITS
#define PM_SET_BITS		9	// 512 sets in the global predictor
#endif
#ifndef PM_WAYS
#define PM_WAYS			4	// ways per set (2 also allowed by the handout)
#endif
#ifndef PM_TAG_BITS
#define PM_TAG_BITS		6	// tag bits per global entry
#endif
#ifndef PM_ADDR_SHIFT
#define PM_ADDR_SHIFT		0	// low address bits dropped before indexing
#endif
#ifndef PM_ALLOC_ON_MISPREDICT
#define PM_ALLOC_ON_MISPREDICT	1	// 1: allocate only if the bimodal table mispredicted
					// 0: allocate on every global miss (handout example)
#endif
#ifndef PM_ALLOC_RESET_COUNTER
#define PM_ALLOC_RESET_COUNTER	1	// 1: new entry starts weakly biased toward the outcome
					// 0: new entry keeps the old counter, then updates it (handout example)
#endif
#define PM_HISTORY_BITS		(PM_SET_BITS + PM_TAG_BITS)

class pm_update : public branch_update {
public:
        unsigned int index;		// bimodal table index
        unsigned int set, tag;		// global predictor set and tag
        int way;			// way that hit, -1 on a global miss
        bool bimodal_prediction;
};

class pm_predictor : public branch_predictor {
public:
        struct global_entry {
                bool valid;
                unsigned char tag;
                unsigned char counter;	// 2-bit saturating counter
                unsigned char age;	// LRU age: 0 = most recently used
        };

        pm_update u;
        branch_info bi;
        unsigned int history;		// global history register (GHR)
        unsigned char bimodal[1<<PM_BIMODAL_BITS];
        global_entry global[1<<PM_SET_BITS][PM_WAYS];

        pm_predictor (void) : history(0) {
                for (int i = 0; i < (1<<PM_BIMODAL_BITS); i++)
                        bimodal[i] = 2;			// weakly taken
                for (int s = 0; s < (1<<PM_SET_BITS); s++)
                        for (int w = 0; w < PM_WAYS; w++) {
                                global[s][w].valid = false;
                                global[s][w].tag = 0;
                                global[s][w].counter = 2;
                                global[s][w].age = PM_WAYS - 1 - w;	// way 0 is the first victim
                        }
        }

        static void update_counter (unsigned char *c, bool taken) {
                if (taken) {
                        if (*c < 3) (*c)++;
                } else {
                        if (*c > 0) (*c)--;
                }
        }

        // make way w the most recently used way of set s
        void touch (unsigned int s, int w) {
                unsigned char old = global[s][w].age;
                for (int i = 0; i < PM_WAYS; i++)
                        if (global[s][i].age < old) global[s][i].age++;
                global[s][w].age = 0;
        }

        // pick a replacement victim: an invalid way if there is one, else the LRU way
        int victim (unsigned int s) {
                int best = 0;
                for (int i = 1; i < PM_WAYS; i++) {
                        global_entry &a = global[s][i], &b = global[s][best];
                        if (a.valid != b.valid ? !a.valid : a.age > b.age) best = i;
                }
                return best;
        }

        branch_update *predict (branch_info & b) {
                bi = b;
                if (b.br_flags & BR_CONDITIONAL) {
                        unsigned int addr = b.address >> PM_ADDR_SHIFT;

                        // bimodal prediction
                        u.index = addr & ((1<<PM_BIMODAL_BITS)-1);
                        u.bimodal_prediction = bimodal[u.index] >> 1;

                        // global predictor lookup
                        unsigned int h = (addr ^ history) & ((1<<PM_HISTORY_BITS)-1);
                        u.set = h >> PM_TAG_BITS;
                        u.tag = h & ((1<<PM_TAG_BITS)-1);
                        u.way = -1;
                        for (int w = 0; PM_GLOBAL && w < PM_WAYS; w++)
                                if (global[u.set][w].valid && global[u.set][w].tag == u.tag) {
                                        u.way = w;
                                        break;
                                }

                        // a global hit overrides the bimodal prediction
                        if (u.way >= 0)
                                u.direction_prediction (global[u.set][u.way].counter >> 1);
                        else
                                u.direction_prediction (u.bimodal_prediction);
                } else {
                        u.direction_prediction (true);
                }

                // branch target prediction is not implemented
                u.target_prediction (0);
                return &u;
        }

        void update (branch_update *bu, bool taken, unsigned int target) {
                if (!(bi.br_flags & BR_CONDITIONAL)) return;
                pm_update *p = (pm_update *) bu;

                // the bimodal table is always trained
                update_counter (&bimodal[p->index], taken);

                if (p->way >= 0) {
                        // global hit: train the entry and mark it MRU
                        update_counter (&global[p->set][p->way].counter, taken);
                        touch (p->set, p->way);
                } else if (PM_GLOBAL && (!PM_ALLOC_ON_MISPREDICT || p->bimodal_prediction != taken)) {
                        // global miss: allocate an entry in the victim way
                        int w = victim (p->set);
                        global_entry &e = global[p->set][w];
                        e.valid = true;
                        e.tag = p->tag;
                        if (PM_ALLOC_RESET_COUNTER)
                                e.counter = taken ? 2 : 1;
                        else
                                update_counter (&e.counter, taken);
                        touch (p->set, w);
                }

                // shift the outcome into the global history register
                history = ((history << 1) | taken) & ((1<<PM_HISTORY_BITS)-1);
        }

};

//
// Complete Pentium M branch predictors for extra credit
// This class implements the complete Pentium M branch prediction units. 
// It implements both branch target prediction and branch outcome predicton. 
class cpm_update : public branch_update {
public:
        unsigned int index;
};

class cpm_predictor : public branch_predictor {
public:
        cpm_update u;

        cpm_predictor (void) {
        }

        branch_update *predict (branch_info & b) {
            u.direction_prediction (true);
            u.target_prediction (0);
            return &u;
        }

        void update (branch_update *u, bool taken, unsigned int target) {
        }

};


