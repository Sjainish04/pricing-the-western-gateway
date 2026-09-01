"""UTTAN Etobicoke-Gardiner congestion-pricing simulation.

A bounded-corridor Stackelberg model of a peak-period congestion charge on the
Gardiner Expressway's western gateway (Hwy 427 to the Humber River).

The package is deliberately layered so each piece can be tested on its own:

    config          model parameters, all in one place
    datasets        loads the public-data CSVs and their provenance
    network         BPR link performance
    demand          traveller segments and base demand
    generalized_cost  the GC_{i,a} term from the proposal
    choice_model    nested logit over the eight follower actions
    congestion      MSA fixed point -> stochastic user equilibrium
    toll_policy     the leader's instrument set
    equity          burden, credits, Suits index, equity score
    finance         gross/net revenue and cost ranges
    metrics         congestion, mobility and emissions indicators
    simulate        one scenario end to end
    game            Stackelberg search, Pigouvian benchmark, Pareto frontier
    site_selection  gateway screening with weight sensitivity
    sensitivity     tornado and Monte Carlo robustness
"""

__version__ = "1.0.0"
