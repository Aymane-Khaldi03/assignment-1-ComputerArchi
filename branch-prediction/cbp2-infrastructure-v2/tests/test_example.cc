// test_example.cc
// Replays the simplified hybrid predictor example from the assignment handout
// (Appendix B) and checks every local prediction, global hit and final
// prediction against the tables in the handout.
//
// Build with the toy configuration (see tests/Makefile):
//   8-bit addresses, 4-bit index taken from address bits [5:2],
//   16-entry bimodal table, 2-way global predictor with 4 sets and 2-bit tags.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "branch.h"
#include "predictor.h"
#include "my_predictor.h"

struct step {
        unsigned int address;
        bool taken;
        bool local;		// expected local (bimodal) prediction
        bool hit;		// expected global hit
        bool final_pred;	// expected final prediction
};

#define B1 0x44
#define B2 0x6C
#define B3 0x90
#define T true
#define N false

// Columns 2, 3, 7 and 8 of the "Hybrid Predictor Results" table.
static const step steps[] = {
        {B1, T, N, N, N}, {B3, T, N, N, N}, {B1, N, T, N, T}, {B2, N, T, N, T},
        {B3, T, N, N, N}, {B1, T, N, T, T}, {B3, T, T, N, T}, {B1, N, T, N, T},
        {B2, N, T, N, T}, {B3, T, T, T, T}, {B1, N, N, T, T}, {B2, T, N, N, N},
        {B1, N, N, N, N}, {B2, N, T, T, N}, {B3, T, T, N, T}, {B1, T, N, T, T},
        {B3, T, T, N, T}, {B1, N, N, N, N}, {B2, N, N, N, N}, {B3, T, T, T, T},
        {B1, T, N, T, T}, {B3, T, T, N, T},
};

// Columns 4 and 6 of the handout's Hybrid Predictor Results (page 8).
static const unsigned int histories[] = {
        0, 1, 3, 6, 12, 9, 3, 7, 14, 12, 9, 2, 5, 10, 4, 9, 3, 7, 14, 12, 9, 3
};
static const unsigned int rows[] = {
        0, 1, 0, 3, 2, 2, 1, 1, 1, 2, 2, 2, 1, 0, 0, 2, 1, 1, 1, 2, 2, 1
};
static const unsigned int tags[] = {
        1, 1, 2, 1, 0, 0, 3, 2, 1, 0, 0, 1, 0, 1, 0, 0, 3, 2, 1, 0, 0, 3
};

int main (void) {
        pm_predictor *p = new pm_predictor ();

        // initial state used in the handout tables
        for (int i = 0; i < 16; i++) p->bimodal[i] = i % 4;
        for (int s = 0; s < 4; s++) {
                p->global[s][0].counter = s;
                p->global[s][1].counter = 3 - s;
        }

        int n = sizeof (steps) / sizeof (steps[0]), errors = 0, miss = 0;
        for (int i = 0; i < n; i++) {
                branch_info b;
                b.address = steps[i].address;
                b.opcode = 0;
                b.br_flags = BR_CONDITIONAL;

                pm_update *u = (pm_update *) p->predict (b);
                bool local = u->bimodal_prediction, hit = u->way >= 0;
                bool final_pred = u->direction_prediction ();
                bool ok = local == steps[i].local && hit == steps[i].hit
                        && final_pred == steps[i].final_pred
                        && p->history == histories[i] && u->set == rows[i] && u->tag == tags[i];
                printf ("%2d addr=0x%02X row=%u tag=%u local=%s %-6s final=%s actual=%s %s\n",
                        i + 1, b.address, u->set, u->tag, local ? "T " : "NT",
                        hit ? "hit" : "nohit", final_pred ? "T " : "NT",
                        steps[i].taken ? "T " : "NT", ok ? "ok" : "MISMATCH");
                errors += !ok;
                miss += final_pred != steps[i].taken;
                p->update (u, steps[i].taken, 0);
        }
        printf ("%d/%d steps match the handout, %d mispredictions\n", n - errors, n, miss);
        delete p;
        return errors || miss != 9 ? 1 : 0;
}
