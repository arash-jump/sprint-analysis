@extends('layouts.app')

@section('content')
<div class="container">
    <h1 class="h3 mb-3">Confirming Training</h1>

    <form action="" method="POST">
        @csrf

        {{-- カレンダー --}}
        <div class="calendar w-100">
            <div class="calendar-header">
                <button type="button" id="prev-month">◀</button>
                    {{date('Y,M')}}
                <button type="button" id="next-month">▶</button>
            </div>

            <table class="calendar-table">
                <thead>
                    <tr>
                        <th>Sun</th>
                        <th>Mon</th>
                        <th>Tue</th>
                        <th>Wed</th>
                        <th>Thu</th>
                        <th>Fri</th>
                        <th>Sut</th>
                    </tr>
                </thead>
                <tbody id="calendar-body">
                    <tr>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                    </tr>
                </tbody>
            </table>

            <div class="selected-info">
                Selected Date：
                <span id="selected-date">Not yet</span>
            </div>

            <input type="hidden" id="date-input" name="date">
        </div>

        {{-- 他の項目 --}}
        <div class="mt-3">
            <label for="title" class="form-label">タイトル</label>
            <input type="text" id="title" name="title" class="form-control">
        </div>

        <button type="submit" class="btn btn-primary mt-3">登録</button>
    </form>
</div>
</div>
@endsection

@push('styles')
<style>
  .calendar {
    width: 320px;
    margin: 20px 0;
    border: 1px solid #ccc;
    border-radius: 8px;
    padding: 10px;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }

  .calendar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .calendar-header button {
    border: none;
    padding: 4px 8px;
    cursor: pointer;
    border-radius: 4px;
    background: #eee;
  }

  .calendar-header button:hover {
    background: #ddd;
  }

  .calendar-header span {
    font-weight: bold;
  }

  table.calendar-table {
    width: 100%;
    border-collapse: collapse;
    text-align: center;
    table-layout: fixed;
    font-size: 14px;
  }

  .calendar-table th,
  .calendar-table td {
    padding: 6px 0;
    border: 1px solid #eee;
  }

  .calendar-table th {
    background: #f5f5f5;
    font-weight: 600;
  }

  .calendar-table td.clickable {
    cursor: pointer;
  }

  .calendar-table td.clickable:hover {
    background: #f0f8ff;
  }

  .calendar-table td.selected {
    background: #4f46e5;
    color: #fff;
    font-weight: bold;
  }

  .selected-info {
    margin-top: 10px;
    font-size: 14px;
    text-align: center;
  }
</style>
@endpush

@push('scripts')
<script>
  const monthYear = document.getElementById('month-year');
  const calendarBody = document.getElementById('calendar-body');
  const selectedDateText = document.getElementById('selected-date');
  const hiddenInput = document.getElementById('date-input');

  let today = new Date();
  let currentYear = today.getFullYear();
  let currentMonth = today.getMonth(); // 0-11

  function renderCalendar(year, month) {
    monthYear.textContent = `${year}年 ${month + 1}月`;
    calendarBody.innerHTML = '';

    const firstDay = new Date(year, month, 1).getDay();
    const lastDate = new Date(year, month + 1, 0).getDate();

    let date = 1;

    for (let i = 0; i < 6; i++) {
      const row = document.createElement('tr');

      for (let j = 0; j < 7; j++) {
        const cell = document.createElement('td');

        if (i === 0 && j < firstDay) {
          cell.textContent = '';
        } else if (date > lastDate) {
          cell.textContent = '';
        } else {
          cell.textContent = date;
          cell.classList.add('clickable');

          const clickedDate = date;

          cell.addEventListener('click', () => {
            document
              .querySelectorAll('.calendar-table td.selected')
              .forEach(td => td.classList.remove('selected'));

            cell.classList.add('selected');

            const ymd =
              year + '-' +
              String(month + 1).padStart(2, '0') + '-' +
              String(clickedDate).padStart(2, '0');

            selectedDateText.textContent = ymd;
            hiddenInput.value = ymd;
          });

          date++;
        }

        row.appendChild(cell);
      }

      calendarBody.appendChild(row);

      if (date > lastDate) {
        break;
      }
    }
  }

  document.getElementById('prev-month').addEventListener('click', () => {
    currentMonth--;
    if (currentMonth < 0) {
      currentMonth = 11;
      currentYear--;
    }
    renderCalendar(currentYear, currentMonth);
  });

  document.getElementById('next-month').addEventListener('click', () => {
    currentMonth++;
    if (currentMonth > 11) {
      currentMonth = 0;
      currentYear++;
    }
    renderCalendar(currentYear, currentMonth);
  });

  // 初期表示（今月）
  renderCalendar(currentYear, currentMonth);
</script>
@endpush
