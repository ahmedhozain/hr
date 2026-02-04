document.addEventListener('DOMContentLoaded',function(){
  // Password toggle
  document.querySelectorAll('.password-toggle').forEach(function(btn){
    if(btn.dataset.init) return; btn.dataset.init='1';
    btn.addEventListener('click',function(){
      var input=document.getElementById('password'); if(!input) return;
      var show=input.type==='password';
      input.type=show?'text':'password';
      this.textContent=show?'إخفاء':'إظهار';
    });
  });

  // Preview modal (client & admin views)
  var modalEl=document.getElementById('previewModal');
  var iframe=document.getElementById('filePreview');
  document.querySelectorAll('.btn-preview').forEach(function(btn){
    if(btn.dataset.init) return; btn.dataset.init='1';
    btn.addEventListener('click',function(){
      var src = btn.getAttribute('data-src');
      if(iframe && src){ iframe.src=src; }
      if(modalEl && typeof bootstrap!=='undefined'){
        var m=bootstrap.Modal.getOrCreateInstance(modalEl);
        m.show();
      }
    });
  });
  if(modalEl && !modalEl.dataset.init){
    modalEl.dataset.init='1';
    modalEl.addEventListener('hidden.bs.modal',function(){ if(iframe) iframe.src=''; });
  }

  // Inline reject panel actions
  document.querySelectorAll('.btn-reject').forEach(function(btn){
    if(btn.dataset.init) return; btn.dataset.init='1';
    btn.addEventListener('click',function(){
      var tr = btn.closest('tr');
      var panelRow = tr ? tr.nextElementSibling : null;
      document.querySelectorAll('tr.reject-row').forEach(function(r){
        if(r !== panelRow){ r.classList.add('d-none'); }
      });
      if(panelRow){
        panelRow.classList.remove('d-none');
        var ta = panelRow.querySelector('textarea');
        if(ta){ setTimeout(function(){ ta.focus(); }, 100); }
      }
    });
  });
  document.querySelectorAll('.btn-cancel-reject').forEach(function(btn){
    if(btn.dataset.init) return; btn.dataset.init='1';
    btn.addEventListener('click',function(){
      var row = btn.closest('tr.reject-row');
      if(row){ row.classList.add('d-none'); }
    });
  });

  // Support notice toast (login)
  var supportBtn=document.getElementById('showSupportNotice');
  var supportNotice=document.getElementById('supportNotice');
  if(supportBtn && supportNotice && !supportBtn.dataset.init){
    supportBtn.dataset.init='1';
    supportBtn.addEventListener('click',function(){
      supportNotice.classList.remove('d-none');
      supportNotice.classList.add('show');
      setTimeout(function(){
        supportNotice.classList.remove('show');
        supportNotice.classList.add('d-none');
      }, 6000);
    });
  }

  // Doc chips navigation (client page)
  document.querySelectorAll('.doc-chip').forEach(function(chip){
    if(chip.dataset.init) return; chip.dataset.init='1';
    chip.addEventListener('click',function(){
      var targetId = chip.getAttribute('data-target');
      var el = targetId ? document.getElementById(targetId) : null;
      if(el){
        el.classList.remove('is-highlighted');
        el.scrollIntoView({ behavior:'smooth', block:'start' });
        setTimeout(function(){
          el.classList.add('is-highlighted');
          setTimeout(function(){ el.classList.remove('is-highlighted'); }, 2000);
        }, 400);
      }
    });
  });

  // Table search filtering (admin tables)
  document.querySelectorAll('.table-search').forEach(function(input){
    if(input.dataset.init) return; input.dataset.init='1';
    var targetSel = input.getAttribute('data-target');
    var table = targetSel ? document.querySelector(targetSel) : null;
    var filter = function(){
      var q = input.value.toLowerCase().trim();
      if(!table) table = targetSel ? document.querySelector(targetSel) : null;
      var rows = table ? table.querySelectorAll('tbody tr') : [];
      rows.forEach(function(tr){
        var text = tr.textContent.toLowerCase();
        tr.style.display = (q === '' || text.indexOf(q) !== -1) ? '' : 'none';
      });
    };
    input.addEventListener('input', filter);
  });
});