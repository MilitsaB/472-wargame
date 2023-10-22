# 472-wargame
This is an implementation of a game called AI Wargame.
Details on the rules of the game are found in the handout provided.

The first deliverable will be available to play in a human vs human version.

After the second deliverable, the game can be played in AI vs human or AI vs AI versions.

Authors:
  Dionisia Poulios - 40131986
  Militsa Bogdeva - 40133261
  David Lemme - 40157270

Deliverable 2 Logic Guide:

- A Tree can initialize, add nodes, traverse in order (sorted by python built-in function)

- minimax finds leaf nodes by recursively calling minimax function,
  then update child's max or min value

- alpha-beta runs e2, when max check for new alpha when min check for new beta
   and if beta<=alpha prune

- suggest_move, generates tree, runs minimax on tree,
  if only minimax, use e1 on node
  if alpha-beta, traverse sorted tree and use e2 on node

- generate_unit_moves performs a move (self destruct only when in combat), 
  calculates heuristic only on leafs, adds game state as node in tree

- generate_game_tree_recursive intializes game tree, recursively calls each child node to   
  generate the game tree (until desired depth)

- e0 : assigns predetermined scores, returns difference of attacker score and defender score

- e1 : assigns weighted scores that are more intuitive to the game semantics,
  and the score takes into account a weighted unit health for each type of player,
  returns difference of scores

- e2 : takes into account e1 components, in addition to the euclidean distance of a Virus to 
  an opponent's AI where bonus scores are given (positive score for Attacker, negative score for Defender) as well as giving more points per valid move possible
  Randomness was added to avoided repeated states

Deliverable 2 Code Guide:

- TreeNode : 278
- Tree: 295
- minimax: 331
- aplhabeta: 372
- ai_move: 650
- branching_factor: 707
- computer_turn: 771
- move_candidates: 808
- suggest_move: 829
- generate_unit_moves: 888
- generate_game_tree_recursive: 939
- e0/heuristic 0: 970
- e1/heuristic 1: 10000
- e2/heuristic 2: 1039

