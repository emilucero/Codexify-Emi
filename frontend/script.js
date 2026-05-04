document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('analyze-form');
    const btn = document.getElementById('submit-btn');
    const resultCard = document.getElementById('result-card');

    // Result elements
    const scoreCircle = document.getElementById('score-circle');
    const scoreValue = document.getElementById('score-value');
    const scoreLabel = document.getElementById('score-label');
    const criticalAlert = document.getElementById('critical-alert');
    const feedbackContent = document.getElementById('feedback-content');
    const metaData = document.getElementById('meta-data');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // UI State: Loading
        btn.classList.add('loading');
        btn.disabled = true;
        resultCard.style.display = 'flex';

        // Reset Result UI
        scoreValue.textContent = '--';
        scoreCircle.setAttribute('stroke-dasharray', `0, 100`);
        scoreLabel.textContent = 'Analisando...';
        scoreLabel.style.color = 'var(--text-muted)';
        criticalAlert.style.display = 'none';
        feedbackContent.innerHTML = '<div style="display:flex; gap:10px; align-items:center"><div class="btn-loader" style="display:block; border-top-color:var(--secondary)"></div> Processando Diff via LangChain...</div>';
        metaData.innerHTML = '';

        // Gather Data
        const payload = {
            project_id: parseInt(document.getElementById('project_id').value, 10),
            mr_external_id: parseInt(document.getElementById('mr_external_id').value, 10),
            author_name: document.getElementById('author_name').value,
            diff_content: document.getElementById('diff_content').value,
        };

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Erro interno no servidor.');
            }

            const data = await response.json();
            // MCP result format parsing
            const resultData = JSON.parse(data.result);

            updateUI(resultData);

        } catch (error) {
            console.error('Error:', error);
            feedbackContent.innerHTML = `<p style="color:var(--danger)"><strong>Erro ao comunicar com MCP:</strong> ${error.message}</p>`;
            scoreLabel.textContent = 'Erro';
            scoreLabel.style.color = 'var(--danger)';
        } finally {
            btn.classList.remove('loading');
            btn.disabled = false;
        }
    });

    function updateUI(data) {
        const score = data.score;

        // Animate score
        let currentScore = 0;
        const targetScore = score;
        const duration = 1500;
        const stepTime = 20;
        const steps = duration / stepTime;
        const increment = targetScore / steps;

        const timer = setInterval(() => {
            currentScore += increment;
            if (currentScore >= targetScore) {
                currentScore = targetScore;
                clearInterval(timer);
            }
            scoreValue.textContent = Math.round(currentScore);
            scoreCircle.setAttribute('stroke-dasharray', `${currentScore}, 100`);
        }, stepTime);

        // Color Logic
        let color = 'var(--success)';
        let label = 'Aprovado';

        if (score <= 50) {
            color = 'var(--danger)';
            label = 'Reprovado';
            criticalAlert.style.display = 'inline-block';
        } else if (score < 80) {
            color = '#eab308'; // Warning yellow
            label = 'Atenção';
        }

        scoreCircle.style.stroke = color;
        scoreLabel.textContent = label;
        scoreLabel.style.color = color;
        scoreValue.style.color = color;

        // Parse Markdown Feedback
        feedbackContent.innerHTML = marked.parse(data.feedback || "Sem feedback detalhado.");

        // Meta Data
        const date = new Date(data.analyzed_at).toLocaleString('pt-BR');
        metaData.innerHTML = `
            <span>MR #${data.mr_external_id} | Projeto ${data.project_id} | Autor: @${data.author_name}</span>
            <span>${date}</span>
        `;
    }
});
