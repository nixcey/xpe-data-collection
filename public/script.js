document.addEventListener('DOMContentLoaded', () => {
  // Upload form and scoreboard display elements
  const uploadForm = document.getElementById('uploadForm');
  const scoreboardInput = document.getElementById('scoreboard');
  const resultSection = document.getElementById('result');
  const mapNameSpan = document.getElementById('mapName');
  const scoreboardTbody = document.querySelector('#scoreboardTable tbody');



  // Team stats elements
  const loadMaleBtn = document.getElementById('loadMaleBtn');
  const loadFemaleBtn = document.getElementById('loadFemaleBtn');
  const maleStatsDiv = document.getElementById('maleStats');
  const femaleStatsDiv = document.getElementById('femaleStats');
  const malePlayersTbody = document.querySelector('#malePlayersTable tbody');
  const maleMapStatsTbody = document.querySelector('#maleMapStatsTable tbody');
  const femalePlayersTbody = document.querySelector('#femalePlayersTable tbody');
  const femaleMapStatsTbody = document.querySelector('#femaleMapStatsTable tbody');

  function populateStatsTable(tbody, data) {
    tbody.innerHTML = '';
    data.forEach(item => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${item.player_name || ''}</td>
        <td>${item.games_played || 0}</td>
        <td>${Number(item.avg_acs || 0).toFixed(2)}</td>
        <td>${Number(item.avg_kills || 0).toFixed(2)}</td>
        <td>${Number(item.avg_deaths || 0).toFixed(2)}</td>
        <td>${Number(item.avg_assists || 0).toFixed(2)}</td>
        <td>${Number(item.avg_econ || 0).toFixed(2)}</td>
        <td>${Number(item.avg_first_bloods || 0).toFixed(2)}</td>
        <td>${Number(item.avg_plants || 0).toFixed(2)}</td>
        <td>${Number(item.avg_defuses || 0).toFixed(2)}</td>
        <td>${item.wins || 0}</td>
        <td>${item.losses || 0}</td>
      `;
      tbody.appendChild(row);
    });
  }

  // Helper function to populate map stats table
  function populateMapStatsTable(tbody, data) {
    tbody.innerHTML = '';
    data.forEach(item => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${item.map || ''}</td>
        <td>${item.total_wins || 0}</td>
        <td>${item.total_losses || 0}</td>
        <td>${item.total_round_wins || 0}</td>
        <td>${item.total_round_losses || 0}</td>
        <td>${item.win_rate || 0}%</td>
        <td>${item.round_win_rate || 0}%</td>
      `;
      tbody.appendChild(row);
    });
  }
  // Upload form handler
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!scoreboardInput.files.length) return alert('Please select an image.');

    const formData = new FormData();
    formData.append('scoreboard', scoreboardInput.files[0]);

    try {
      const res = await fetch('/upload', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) throw new Error('Upload failed.');

      const data = await res.json();

      if (data.error) {
        alert('Error: ' + data.error);
        return;
      }

      displayScoreboardData(data);
    } catch (err) {
      alert('Error uploading or processing image: ' + err.message);
    }
  });

  function displayScoreboardData(data) {
    mapNameSpan.textContent = data.map || 'Unknown';

    scoreboardTbody.innerHTML = '';
    data.players.forEach(player => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${player.Player || ''}</td>
        <td>${player.ACS || 0}</td>
        <td>${player.K || 0}</td>
        <td>${player.D || 0}</td>
        <td>${player.A || 0}</td>
        <td>${player.ECON || 0}</td>
        <td>${player["FIRST BLOODS"] || 0}</td>
        <td>${player.PLANTS || 0}</td>
        <td>${player.DEFUSES || 0}</td>
      `;
      scoreboardTbody.appendChild(row);
    });

    resultSection.classList.remove('hidden');
  }


  // Team visibility functions
  function showMaleStats() {
    maleStatsDiv.classList.remove('hidden');
    femaleStatsDiv.classList.add('hidden');
  }

  function showFemaleStats() {
    femaleStatsDiv.classList.remove('hidden');
    maleStatsDiv.classList.add('hidden');
  }

  // Load male team handler
  loadMaleBtn.addEventListener('click', async () => {
    try {
      const res = await fetch('/male_team');
      if (!res.ok) throw new Error('Failed to fetch male team stats');
      
      const data = await res.json();
      
      populateStatsTable(malePlayersTbody, data.players);
      populateMapStatsTable(maleMapStatsTbody, data.maps);
      
      document.getElementById('malePlayersTable').classList.remove('hidden');
      document.getElementById('maleMapStatsTable').classList.remove('hidden');
      showMaleStats();
    } catch (err) {
      alert('Error loading male team stats: ' + err.message);
    }
  });

  // Load female team handler
  loadFemaleBtn.addEventListener('click', async () => {
    try {
      const res = await fetch('/female_team');
      if (!res.ok) throw new Error('Failed to fetch female team stats');
      
      const data = await res.json();
      
      populateStatsTable(femalePlayersTbody, data.players);
      populateMapStatsTable(femaleMapStatsTbody, data.maps);
      
      document.getElementById('femalePlayersTable').classList.remove('hidden');
      document.getElementById('femaleMapStatsTable').classList.remove('hidden');
      showFemaleStats();
    } catch (err) {
      alert('Error loading female team stats: ' + err.message);
    }
  });
});