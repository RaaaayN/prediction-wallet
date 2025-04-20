<!-- transactions.php -->
<?php
session_start();
if (!isset($_SESSION['user_id'])) { header('Location: login.html'); exit; }
require 'db.php';
$userId = $_SESSION['user_id'];
$stmt = $pdo->prepare("SELECT * FROM transactions WHERE user_id = ? ORDER BY occurred_at DESC");
$stmt->execute([$userId]);
$transactions = $stmt->fetchAll();
?>
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Historique</title><link rel="stylesheet" href="style.css"></head>
<body>
  <header><h1>Historique des Transactions</h1></header>
  <main>
    <table>
      <thead><tr><th>Date</th><th>Type</th><th>Montant</th><th>Catégorie</th><th>Description</th></tr></thead>
      <tbody>
      <?php foreach ($transactions as $tx): ?>
        <tr>
          <td><?= htmlspecialchars($tx['occurred_at']) ?></td>
          <td><?= htmlspecialchars($tx['type']) ?></td>
          <td><?= number_format($tx['amount'],2,',',' ') ?></td>
          <td><?= htmlspecialchars($tx['category']) ?></td>
          <td><?= htmlspecialchars($tx['description']) ?></td>
        </tr>
      <?php endforeach; ?>
      </tbody>
    </table>
  </main>
</body>
</html>