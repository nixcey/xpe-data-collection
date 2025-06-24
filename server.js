const express = require('express');
const multer = require('multer');
const path = require('path');
const { execFile } = require('child_process');
const mysql = require('mysql2/promise');
const fs = require('fs');

const app = express();
const PORT = 3030;

const dbConfig = {
  host: 'localhost',
  user: 'root',
  password: 'root',
  database: 'valorant'
};

const upload = multer({ dest: 'uploads/' });

const MALE_PLAYERS = new Set(['XPE nixcey', 'XPE Burger', 'Drahmenn', 'Loveleiy', 'Walid']);
const FEMALE_PLAYERS = new Set(['XPE Buttercup', 'sawako', 'XPE roro', 'XPE Grass', 'distressed']);

async function processInterTeamMatch(connection, {gameId, mapName, winner, team1Players, team2Players, t1Rounds, t2Rounds}) {
  // Determine which team is male and which is female
  const maleTeam = team1Players.some(p => MALE_PLAYERS.has(p.Player)) ? 'team1' : 'team2';
  const femaleTeam = maleTeam === 'team1' ? 'team2' : 'team1';
  
  const malePlayers = maleTeam === 'team1' ? team1Players : team2Players;
  const femalePlayers = femaleTeam === 'team1' ? team1Players : team2Players;
  
  const maleWon = (maleTeam === 'team1' && winner === 'Team 1') || 
                 (maleTeam === 'team2' && winner === 'Team 2');
  
  // Process male team stats
  for (const player of malePlayers) {
    await connection.execute(
      `INSERT INTO male_team_stats (...) VALUES (...)`,
      [
        gameId, player.Player, mapName, player.ACS, player.K, player.D, player.A, 
        player.ECON, player["FIRST BLOODS"], player.PLANTS, player.DEFUSES,
        maleWon ? 1 : 0,  // wins
        maleWon ? 0 : 1,  // losses
        maleTeam === 'team1' ? t1Rounds : t2Rounds,  // round_wins
        maleTeam === 'team1' ? t2Rounds : t1Rounds   // round_losses
      ]
    );
  }
  
  // Process female team stats
  for (const player of femalePlayers) {
    await connection.execute(
      `INSERT INTO female_team_stats (...) VALUES (...)`,
      [
        gameId, player.Player, mapName, player.ACS, player.K, player.D, player.A, 
        player.ECON, player["FIRST BLOODS"], player.PLANTS, player.DEFUSES,
        maleWon ? 0 : 1,  // wins
        maleWon ? 1 : 0,  // losses
        femaleTeam === 'team1' ? t1Rounds : t2Rounds,  // round_wins
        femaleTeam === 'team1' ? t2Rounds : t1Rounds   // round_losses
      ]
    );
  }
  
  // Update map stats for both teams
  await updateMapStats(connection, 'male', mapName, maleWon, t1Rounds, t2Rounds);
  await updateMapStats(connection, 'female', mapName, !maleWon, t1Rounds, t2Rounds);
}

async function updateMapStats(connection, team, map, won, t1Rounds, t2Rounds) {
  const [existing] = await connection.execute(
    `SELECT * FROM team_map_stats WHERE team = ? AND map = ?`,
    [team, map]
  );
  
  if (existing.length > 0) {
    await connection.execute(
      `UPDATE team_map_stats SET
        total_wins = total_wins + ?,
        total_losses = total_losses + ?,
        total_round_wins = total_round_wins + ?,
        total_round_losses = total_round_losses + ?
       WHERE team = ? AND map = ?`,
      [
        won ? 1 : 0,
        won ? 0 : 1,
        won ? t1Rounds : t2Rounds,
        won ? t2Rounds : t1Rounds,
        team, map
      ]
    );
  } else {
    await connection.execute(
      `INSERT INTO team_map_stats (...) VALUES (...)`,
      [
        team, map,
        won ? 1 : 0,
        won ? 0 : 1,
        won ? t1Rounds : t2Rounds,
        won ? t2Rounds : t1Rounds
      ]
    );
  }
}

// Helper function to detect which team this game belongs to based on IGL presence & winner
function detectTeam(players, winner, team1Players, team2Players) {
  // Check male IGL (Drahmenn)
  const maleIGL = "Drahmenn";
  const femaleIGL = "XPE roro";
  
  const team1HasMaleIGL = team1Players.some(p => p.Player === maleIGL);
  const team2HasMaleIGL = team2Players.some(p => p.Player === maleIGL);
  
  if (team1HasMaleIGL || team2HasMaleIGL) return "male";
  
  // Check female IGL (XPE roro)
  const team1HasFemaleIGL = team1Players.some(p => p.Player === femaleIGL);
  const team2HasFemaleIGL = team2Players.some(p => p.Player === femaleIGL);
  
  if (team1HasFemaleIGL || team2HasFemaleIGL) return "female";
  
  return "unknown";
}

function isInterTeamMatch(team1Players, team2Players) {
  const team1MaleCount = team1Players.filter(p => MALE_PLAYERS.has(p.Player)).length;
  const team1FemaleCount = team1Players.filter(p => FEMALE_PLAYERS.has(p.Player)).length;
  const team2MaleCount = team2Players.filter(p => MALE_PLAYERS.has(p.Player)).length;
  const team2FemaleCount = team2Players.filter(p => FEMALE_PLAYERS.has(p.Player)).length;

  // If one team has male players and the other has female players
  return (team1MaleCount > 0 && team2FemaleCount > 0) || 
         (team1FemaleCount > 0 && team2MaleCount > 0);
}

app.use(express.static('public'));

app.post('/upload', upload.single('scoreboard'), async (req, res) => {
  const imagePath = req.file.path;
  console.log('Processing image:', imagePath);

  try {
    const scriptPath = path.join(__dirname, 'extract_scoreboard.py');
    console.log('Python script path:', scriptPath);

    execFile('python', [scriptPath, imagePath], async (error, stdout, stderr) => {
      console.log('Python stdout:', stdout);
      console.log('Python stderr:', stderr);
      fs.unlinkSync(imagePath);

      if (error) {
        console.error('Python error:', stderr);
        return res.status(500).json({ error: 'Python processing failed.' });
      }

      let data;
      try {
        data = JSON.parse(stdout);
      } catch (parseErr) {
        console.error('JSON parse error:', parseErr);
        return res.status(500).json({ error: 'Invalid JSON from Python script.' });
      }

      const players = data.players;
      const mapName = data.map || null;
      const winner = data.winner;
      
      // Separate team1 and team2 players based on scoreboard order (first 5 and last 5)
      const team1Players = players.slice(0, 5).filter(p => 
        MALE_PLAYERS.has(p.Player) || FEMALE_PLAYERS.has(p.Player)
      );
      const team2Players = players.slice(5, 10).filter(p => 
        MALE_PLAYERS.has(p.Player) || FEMALE_PLAYERS.has(p.Player)
      );

      console.log('Players:', players);
      console.log('Team 1 players:', team1Players);
      console.log('Team 2 players:', team2Players);

      // Check if this is an inter-team match (male vs female)
      const isInterTeamMatch = checkInterTeamMatch(team1Players, team2Players);

      try {
        const connection = await mysql.createConnection(dbConfig);
        console.log('Successfully connected to database');

        // Insert new game row with map
        const [gameResult] = await connection.execute(
          `INSERT INTO games (map, is_inter_team) VALUES (?, ?)`, 
          [mapName, isInterTeamMatch ? 1 : 0]
        );
        const gameId = gameResult.insertId;

        // Get total rounds per team for round wins/losses
        const t1Rounds = data.team1_rounds || 0;
        const t2Rounds = data.team2_rounds || 0;

        if (isInterTeamMatch) {
          // Process inter-team match (male vs female)
          await processInterTeamMatch(connection, {
            gameId,
            mapName,
            winner,
            team1Players,
            team2Players,
            t1Rounds,
            t2Rounds
          });
        } else {
          // Process regular match (single team)
          const teamType = detectTeam(players, winner, team1Players, team2Players);
          if (!teamType) {
            await connection.end();
            return res.status(400).json({ error: "Could not determine team type (male/female)." });
          }

          await processRegularMatch(connection, {
            gameId,
            mapName,
            winner,
            players,
            teamType,
            t1Rounds,
            t2Rounds
          });
        }

        await connection.end();
        res.json({ 
          success: true, 
          game_id: gameId, 
          map: mapName, 
          players, 
          is_inter_team: isInterTeamMatch 
        });
      } catch (dbErr) {
        console.error('DB error:', dbErr);
        res.status(500).json({ error: 'Database insert failed.' });
      }
    });
  } catch (err) {
    res.status(500).json({ error: 'Server error.' });
  }
});

// Helper functions
function checkInterTeamMatch(team1Players, team2Players) {
  const team1MaleCount = team1Players.filter(p => MALE_PLAYERS.has(p.Player)).length;
  const team1FemaleCount = team1Players.filter(p => FEMALE_PLAYERS.has(p.Player)).length;
  const team2MaleCount = team2Players.filter(p => MALE_PLAYERS.has(p.Player)).length;
  const team2FemaleCount = team2Players.filter(p => FEMALE_PLAYERS.has(p.Player)).length;

  // If one team has male players and the other has female players
  return (team1MaleCount > 0 && team2FemaleCount > 0) || 
         (team1FemaleCount > 0 && team2MaleCount > 0);
}

async function processInterTeamMatch(connection, {gameId, mapName, winner, team1Players, team2Players, t1Rounds, t2Rounds}) {
  // Determine which team is male and which is female
  const maleTeam = team1Players.some(p => MALE_PLAYERS.has(p.Player)) ? 'team1' : 'team2';
  const femaleTeam = maleTeam === 'team1' ? 'team2' : 'team1';
  
  const malePlayers = maleTeam === 'team1' ? team1Players : team2Players;
  const femalePlayers = femaleTeam === 'team1' ? team1Players : team2Players;
  
  const maleWon = (maleTeam === 'team1' && winner === 'Team 1') || 
                 (maleTeam === 'team2' && winner === 'Team 2');
  
  // Process male team stats
  for (const player of malePlayers) {
    await connection.execute(
      `INSERT INTO male_team_stats (
        game_id, player_name, map, acs, kills, deaths, assists, econ, 
        first_bloods, plants, defuses, wins, losses, round_wins, round_losses
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        gameId, player.Player, mapName, player.ACS, player.K, player.D, player.A, 
        player.ECON, player["FIRST BLOODS"], player.PLANTS, player.DEFUSES,
        maleWon ? 1 : 0,  // wins
        maleWon ? 0 : 1,  // losses
        maleTeam === 'team1' ? t1Rounds : t2Rounds,  // round_wins
        maleTeam === 'team1' ? t2Rounds : t1Rounds   // round_losses
      ]
    );
  }
  
  // Process female team stats
  for (const player of femalePlayers) {
    await connection.execute(
      `INSERT INTO female_team_stats (
        game_id, player_name, map, acs, kills, deaths, assists, econ, 
        first_bloods, plants, defuses, wins, losses, round_wins, round_losses
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        gameId, player.Player, mapName, player.ACS, player.K, player.D, player.A, 
        player.ECON, player["FIRST BLOODS"], player.PLANTS, player.DEFUSES,
        maleWon ? 0 : 1,  // wins
        maleWon ? 1 : 0,  // losses
        femaleTeam === 'team1' ? t1Rounds : t2Rounds,  // round_wins
        femaleTeam === 'team1' ? t2Rounds : t1Rounds   // round_losses
      ]
    );
  }
  
  // Update map stats for both teams
  await updateMapStats(connection, 'male', mapName, maleWon, t1Rounds, t2Rounds);
  await updateMapStats(connection, 'female', mapName, !maleWon, t1Rounds, t2Rounds);
}

async function processRegularMatch(connection, {gameId, mapName, winner, players, teamType, t1Rounds, t2Rounds}) {
  const teamStatsTable = teamType === 'male' ? 'male_team_stats' : 'female_team_stats';
  const teamPlayers = players.filter(p => 
    teamType === 'male' ? MALE_PLAYERS.has(p.Player) : FEMALE_PLAYERS.has(p.Player)
  );

  // Determine winning players and losing players based on winner string
  const winningPlayers = winner === "Team 1" ? players.slice(0,5) : players.slice(5,10);

  // Insert player stats in the correct team table
  for (const player of teamPlayers) {
    const isWinner = winningPlayers.some(p => p.Player === player.Player);
    await connection.execute(
      `INSERT INTO ${teamStatsTable} (
        game_id, player_name, map, acs, kills, deaths, assists, econ, 
        first_bloods, plants, defuses, wins, losses, round_wins, round_losses
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        gameId, player.Player, mapName, player.ACS, player.K, player.D, player.A,
        player.ECON, player["FIRST BLOODS"], player.PLANTS, player.DEFUSES,
        isWinner ? 1 : 0,  // wins
        isWinner ? 0 : 1,  // losses
        isWinner ? t1Rounds : t2Rounds,  // round_wins
        isWinner ? t2Rounds : t1Rounds   // round_losses
      ]
    );
  }

  // Update team aggregate stats
  const IGLplayer = teamType === 'male' ? "Drahmenn" : "XPE roro";
  const IGLonWinningTeam = winningPlayers.some(p => p.Player === IGLplayer);
  await updateMapStats(connection, teamType, mapName, IGLonWinningTeam, t1Rounds, t2Rounds);
}

async function updateMapStats(connection, team, map, won, t1Rounds, t2Rounds) {
  const [existing] = await connection.execute(
    `SELECT * FROM team_map_stats WHERE team = ? AND map = ?`,
    [team, map]
  );
  
  if (existing.length > 0) {
    await connection.execute(
      `UPDATE team_map_stats SET
        total_wins = total_wins + ?,
        total_losses = total_losses + ?,
        total_round_wins = total_round_wins + ?,
        total_round_losses = total_round_losses + ?
       WHERE team = ? AND map = ?`,
      [
        won ? 1 : 0,
        won ? 0 : 1,
        won ? t1Rounds : t2Rounds,
        won ? t2Rounds : t1Rounds,
        team, map
      ]
    );
  } else {
    await connection.execute(
      `INSERT INTO team_map_stats (
        team, map, total_wins, total_losses, total_round_wins, total_round_losses
      ) VALUES (?, ?, ?, ?, ?, ?)`,
      [
        team, map,
        won ? 1 : 0,
        won ? 0 : 1,
        won ? t1Rounds : t2Rounds,
        won ? t2Rounds : t1Rounds
      ]
    );
  }
}


// Update both /male_team and /female_team endpoints similarly:
app.get('/male_team', async (req, res) => {
  try {
    const connection = await mysql.createConnection(dbConfig);

  const [players] = await connection.execute(`
    SELECT 
      player_name,
      COUNT(*) AS games_played,
      AVG(acs) AS avg_acs,
      /* other stats */
      SUM(wins) AS wins,
      SUM(losses) AS losses,
      ROUND(SUM(wins) / COUNT(*) * 100, 1) AS win_rate,
      SUM(round_wins) AS total_round_wins,
      SUM(round_losses) AS total_round_losses,
      ROUND(SUM(round_wins) / (SUM(round_wins) + SUM(round_losses)) * 100, 1) AS round_win_rate
    FROM male_team_stats
    GROUP BY player_name
    ORDER BY avg_acs DESC
  `);

  const [maps] = await connection.execute(`
    SELECT 
      map,
      total_wins,
      total_losses,
      ROUND(total_wins / (total_wins + total_losses) * 100, 1) AS win_rate,
      total_round_wins,
      total_round_losses,
      ROUND(total_round_wins / (total_round_wins + total_round_losses) * 100, 1) AS round_win_rate
    FROM team_map_stats
    WHERE team = 'male'
  `);

    await connection.end();
    
    res.json({ 
      players: players.map(p => ({
        ...p,
        avg_acs: Number(p.avg_acs || 0),
        // Convert all averages to numbers
      })),
      maps 
    });
  } catch (err) {
    console.error('DB error:', err);
    res.status(500).json({ error: 'Failed to fetch male team stats.' });
  }
});

// Update both /male_team and /female_team endpoints similarly:
app.get('/female_team', async (req, res) => {
  try {
    const connection = await mysql.createConnection(dbConfig);

  const [players] = await connection.execute(`
    SELECT 
      player_name,
      COUNT(*) AS games_played,
      AVG(acs) AS avg_acs,
      /* other stats */
      SUM(wins) AS wins,
      SUM(losses) AS losses,
      ROUND(SUM(wins) / COUNT(*) * 100, 1) AS win_rate,
      SUM(round_wins) AS total_round_wins,
      SUM(round_losses) AS total_round_losses,
      ROUND(SUM(round_wins) / (SUM(round_wins) + SUM(round_losses)) * 100, 1) AS round_win_rate
    FROM female_team_stats
    GROUP BY player_name
    ORDER BY avg_acs DESC
  `);

  const [maps] = await connection.execute(`
    SELECT 
      map,
      total_wins,
      total_losses,
      ROUND(total_wins / (total_wins + total_losses) * 100, 1) AS win_rate,
      total_round_wins,
      total_round_losses,
      ROUND(total_round_wins / (total_round_wins + total_round_losses) * 100, 1) AS round_win_rate
    FROM team_map_stats
    WHERE team = 'female'
  `);

    await connection.end();
    
    res.json({ 
      players: players.map(p => ({
        ...p,
        avg_acs: Number(p.avg_acs || 0),
        // Convert all averages to numbers
      })),
      maps 
    });
  } catch (err) {
    console.error('DB error:', err);
    res.status(500).json({ error: 'Failed to fetch female team stats.' });
  }
});


app.listen(PORT, () => console.log(`Server running at http://localhost:${PORT}`));